import os
import requests
import json
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
from openai import OpenAI
import inspect
import re

# 初始化 Flask
app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_default_secret_key")  # 用于 Session 认证

# OpenAI API 初始化
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 访问密码
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "hanliangdeng")  # 默认密码

# API Keys
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")  # OpenWeather API Key
NEWS_API_KEY = os.environ["NEWS_API_KEY"]

# 限制对话历史长度
MAX_HISTORY = 20


### ========================== 1️⃣ 登录 & 退出 ========================== ###

@app.route('/')
def index():
    return render_template('login.html')  # 渲染登录页面

@app.route('/login', methods=['POST'])
def login():
    password = request.form.get('password')
    if password == ACCESS_TOKEN:
        session["authenticated"] = True  # 设置用户已登录
        return redirect(url_for('chat_page'))
    else:
        return render_template('login.html', error="Invalid password")

@app.route('/logout', methods=['POST'])
def logout():
    session.pop("authenticated", None)
    return redirect(url_for('index'))


### ========================== 2️⃣  聊天页面 ========================== ###

@app.route('/chat')
def chat_page():
    if not session.get("authenticated"):
        return redirect(url_for('index'))  # 未登录用户重定向回登录页
    return render_template('chat.html')


### ========================== 3️⃣ 实时天气查询（基于 OpenWeather API） ========================== ###

def query_openweather_function(city="Beijing", units="metric", language="zh_cn",
                               api_key=None, ):
    """
    使用OpenWeather API查询指定城市的实时天气信息，并将结果以JSON格式的字符串返回。

    参数:
    city (str): 必填参数。需要查询天气的城市，默认为北京,如果输入的地区是中国的中文字符，就换成对应的英文名称，如北京市，正确的输入应该为"beijing"
    units (str): 计量单位，默认为摄氏度（metric）。
    language (str): 输出信息的语言，默认为简体中文（zh_cn）。
    api_key (str): 用于访问OpenWeather的API密钥。

    返回:
    str: 查询到的天气信息，以JSON格式的字符串返回。如果查询失败，返回包含错误信息的JSON格式字符串。
    """

    api_key = os.getenv("OPENWEATHER_API_KEY")

    if not api_key or api_key == "your_openweather_api_key":
        print("❌ OpenWeather API Key 未设置或无效")
        return json.dumps({"error": "OpenWeather API Key is missing or invalid."})

    # 构建请求的URL
    url = "https://api.openweathermap.org/data/2.5/weather"

    # 设置查询参数
    params = {
        "q": city,
        "appid": api_key,
        "units": units,
        "lang": language
    }

    # 发送GET请求
    response = requests.get(url, params=params)

    # 检查响应状态
    if response.status_code == 200:
        # 解析响应数据
        data = response.json()
        print("✅ OpenWeather API 响应:", data)  # 打印 API 返回数据

        # 将结果转换为JSON格式的字符串
        return json.dumps(data)
    else:
        # 创建一个错误消息
        error_message = {
            "错误": f"查询失败，状态码：{response.status_code}",
            "响应数据": response.text
        }

        print("❌ OpenWeather API 错误:", error_message)
        # 将错误消息转换为JSON格式的字符串
        return json.dumps(error_message)


### ========================== 3️⃣ 实时新闻查询（基于 NewsAPI） ========================== ###
def query_news_function(topic="technology", language="zh", page_size=5, api_key=None):
    """
    使用 NewsAPI 查询指定主题的最新新闻，并限制返回的新闻条数。

    参数:
    - topic (str): 需要查询的新闻主题，默认为 "technology"。
    - language (str): 新闻语言，默认为 "zh"（简体中文）。
    - page_size (int): 需要返回的新闻数量，默认为 5。
    - api_key (str): NewsAPI 的 API 密钥。

    返回:
    - str: 查询到的新闻信息，以 JSON 格式返回。
    """
    api_key = os.getenv("NEWS_API_KEY")  # 获取 API Key

    if not api_key or api_key == "your_news_api_key":
        print("❌ NewsAPI Key 未设置或无效")
        return json.dumps({"error": "NewsAPI Key is missing or invalid."})

    url = "https://newsapi.org/v2/everything"

    params = {
        "q": topic,
        "language": language,
        "pageSize": page_size,  # 限制返回条数
        "apiKey": api_key
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        articles = data.get("articles", [])

        # 只返回简短的标题和来源，避免 Token 过载
        news_summary = [
            {
                "title": article.get("title", "无标题"),
                "source": article["source"].get("name", "未知来源"),
                "url": article.get("url", "#")
            }
            for article in articles
        ]

        return json.dumps(news_summary)
    else:
        error_message = {
            "错误": f"查询失败，状态码：{response.status_code}",
            "响应数据": response.text
        }
        print("❌ NewsAPI 错误:", error_message)
        return json.dumps(error_message)



### ========================== 4️⃣ OpenAI Function Calling 机制 ========================== ###

class AutoFunctionGenerator:
    """
    AutoFunctionGenerator 类用于自动生成一系列功能函数的 JSON Schema 描述。
    该类通过调用 OpenAI API，采用 Few-shot learning 的方式来生成这些描述。

    属性:
    - functions_list (list): 一个包含多个功能函数的列表。
    - max_attempts (int): 最大尝试次数，用于处理 API 调用失败的情况。

    方法:
    - __init__ : 初始化 AutoFunctionGenerator 类。
    - generate_function_descriptions : 自动生成功能函数的 JSON Schema 描述。
    - _call_openai_api : 调用 OpenAI API。
    - auto_generate : 自动生成功能函数的 JSON Schema 描述，并处理任何异常。
    """

    def __init__(self, functions_list, max_attempts=3):
        """
        初始化 AutoFunctionGenerator 类。

        参数:
        - functions_list (list): 一个包含多个功能函数的列表。
        - max_attempts (int): 最大尝试次数。
        """
        self.functions_list = functions_list
        self.max_attempts = max_attempts

    def generate_function_descriptions(self):
        """
        自动生成功能函数的 JSON Schema 描述。

        返回:
        - list: 包含 JSON Schema 描述的列表。
        """
        # 创建空列表，保存每个功能函数的JSON Schema描述
        functions = []

        for function in self.functions_list:
            # 读取指定函数的函数说明
            function_description = inspect.getdoc(function)

            # 读取函数的函数名
            function_name = function.__name__

            # 定义system role的Few-shot提示
            system_Q = "你是一位优秀的数据分析师，现在有一个函数的详细声明如下：%s" % function_description
            system_A = "计算年龄总和的函数，该函数从一个特定格式的JSON字符串中解析出DataFrame，然后计算所有人的年龄总和并以JSON格式返回结果。\
                        \n:param input_json: 必要参数，要求字符串类型，表示含有个体年龄数据的JSON格式字符串 \
                        \n:return: 计算完成后的所有人年龄总和，返回结果为JSON字符串类型对象"

            # 定义user role的Few-shot提示
            user_Q = "请根据这个函数声明，为我生成一个JSON Schema对象描述。这个描述应该清晰地标明函数的输入和输出规范。具体要求如下：\
                      1. 提取函数名称：%s，并将其用作JSON Schema中的'name'字段  \
                      2. 在JSON Schema对象中，设置函数的参数类型为'object'.\
                      3. 'properties'字段如果有参数，必须表示出字段的描述. \
                      4. 从函数声明中解析出函数的描述，并在JSON Schema中以中文字符形式表示在'description'字段.\
                      5. 识别函数声明中哪些参数是必需的，然后在JSON Schema的'required'字段中列出这些参数. \
                      6. 输出的应仅为符合上述要求的JSON Schema对象内容,不需要任何上下文修饰语句. " % function_name

            user_A = "{'name': 'calculate_total_age_function', \
                               'description': '计算年龄总和的函数，从给定的JSON格式字符串（按'split'方向排列）中解析出DataFrame，计算所有人的年龄总和，并以JSON格式返回结果。 \
                               'parameters': {'type': 'object', \
                                              'properties': {'input_json': {'description': '执行计算年龄总和的数据集', 'type': 'string'}}, \
                                              'required': ['input_json']}}"

            # 定义输入

            system_message = "你是一位优秀的数据分析师，现在有一个函数的详细声明如下：%s" % function_description
            user_message = "请根据这个函数声明，为我生成一个JSON Schema对象描述。这个描述应该清晰地标明函数的输入和输出规范。具体要求如下：\
                            1. 提取函数名称：%s，并将其用作JSON Schema中的'name'字段  \
                            2. 在JSON Schema对象中，设置函数的参数类型为'object'.\
                            3. 'properties'字段如果有参数，必须表示出字段的描述. \
                            4. 从函数声明中解析出函数的描述，并在JSON Schema中以中文字符形式表示在'description'字段.\
                            5. 识别函数声明中哪些参数是必需的，然后在JSON Schema的'required'字段中列出这些参数. \
                            6. 输出的应仅为符合上述要求的JSON Schema对象内容,不需要任何上下文修饰语句. " % function_name

            messages = [
                {"role": "system", "content": "Q:" + system_Q + user_Q + "A:" + system_A + user_A},

                {"role": "user", "content": 'Q:' + system_message + user_message}
            ]

            response = self._call_openai_api(messages)

            if response is None:
                print("❌ 错误: API 返回 None")
                return []

            if not hasattr(response, "choices") or not response.choices:
                print("❌ 错误: API 响应无 choices 字段")
                return []

            if not response or not response.choices:
                print("Error: OpenAI API 返回的 response 为空")
                continue

            content = response.choices[0].message.content.strip()

            if not content:
                print("Error: OpenAI API 返回的 content 为空")
                continue

            try:
                # **去除 Markdown 代码块** (防止 `json.loads()` 解析失败)
                cleaned_content = re.sub(r"^```json\n|\n```$", "", content)

                print("🔵 解析后的 JSON Schema:", cleaned_content)

                schema_json = json.loads(cleaned_content)  # 解析 JSON
                functions.append(schema_json)  # 存储到列表

            except json.JSONDecodeError as e:
                print(f"❌ JSONDecodeError: {e}")
                print(f"API response content: {content}")  # 打印 API 返回的内容
                continue

        return functions

    def _call_openai_api(self, messages):
        """
        私有方法，用于调用 OpenAI API。

        参数:
        - messages (list): 包含 API 所需信息的消息列表。

        返回:
        - object: API 调用的响应对象。
        """
        # 请根据您的实际情况修改此处的 API 调用
        return client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
        )

    def auto_generate(self):
        """
        自动生成功能函数的 JSON Schema 描述，并处理任何异常。

        返回:
        - list: 包含 JSON Schema 描述的列表。

        异常:
        - 如果达到最大尝试次数，将抛出异常。
        """
        attempts = 0
        while attempts < self.max_attempts:
            try:
                functions = self.generate_function_descriptions()
                return functions
            except Exception as e:
                attempts += 1
                print(f"Error occurred: {e}")
                if attempts >= self.max_attempts:
                    print("Reached maximum number of attempts. Terminating.")
                    raise
                else:
                    print("Retrying...")


### ========================== 5️⃣ GPT-4o Chatbot（支持记忆 & 实时数据） ========================== ###


@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        if not session.get("authenticated"):
            return jsonify({"error": "Unauthorized access"}), 401  # 未授权用户禁止访问

        user_input = request.json.get('message', '').strip()
        if not user_input:
            return jsonify({"error": "Message cannot be empty"}), 400

        # 解析 Function Calling
        function_list = [query_openweather_function, query_news_function]  # 需要 GPT-4o 调用的外部函数
        generator = AutoFunctionGenerator(function_list)  # 生成 JSON Schema
        functions = generator.auto_generate()
        print("Generated function descriptions:", functions)

        # **检查 functions 是否为空**
        if not functions:
            return jsonify({"error": "Function descriptions are empty."}), 500

        session.setdefault("conversation_history", [])  # 确保对话历史存在
        session["conversation_history"].append({"role": "user", "content": user_input})

        # **第一次调用 GPT-4o**
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=session["conversation_history"],
            functions=functions,
            function_call="auto"
        )

        # **打印 OpenAI API 响应**
        print("🟢 OpenAI API Response:", response)

        response_message = response.choices[0].message

        # **存储 GPT 响应时转换为字典**
        session["conversation_history"].append({
            "role": response_message.role,
            "content": response_message.content if response_message.content else "",
            "function_call": {
                "name": response_message.function_call.name if response_message.function_call else None,
                "arguments": response_message.function_call.arguments if response_message.function_call else None,
            } if response_message.function_call else None
        })

        # **检查是否需要调用外部函数**
        if response_message.function_call:
            function_name = response_message.function_call.name
            function_args = json.loads(response_message.function_call.arguments)

            print(f"✅ 触发 Function Calling: {function_name}，参数: {function_args}")

            # **调用不同 API**
            if function_name == "query_openweather_function":
                function_response = query_openweather_function(**function_args)
            elif function_name == "query_news_function":
                function_response = query_news_function(**function_args)

                # **解析新闻数据，限制 GPT 处理的数量**
                news_list = json.loads(function_response)
                if isinstance(news_list, list):
                    news_text = "\n".join([
                        f"{i + 1}. {n['title']}（来源: {n['source']}）\n阅读详情: {n['url']}"
                        for i, n in enumerate(news_list[:5])  # 只取前 5 条新闻
                    ])
                    function_response = json.dumps({"summary": news_text})  # 让 GPT 只总结 5 条新闻

            else:
                function_response = json.dumps({"error": f"未知函数: {function_name}"})

            function_response_json = json.dumps(function_response)  # 确保是 JSON 字符串

            # 存储函数调用的返回值
            session["conversation_history"].append({
                "role": "function",
                "name": function_name,
                "content": function_response_json
            })

            # **第二次调用 GPT-4o，让它处理函数调用的返回值**
            second_response = client.chat.completions.create(
                model="gpt-4o",
                messages=session["conversation_history"]
            )

            bot_reply = second_response.choices[0].message.content
        else:
            print("❌ OpenAI 未触发 Function Calling，返回普通聊天内容")
            bot_reply = response_message.content  # 直接返回 GPT 回答

        # **更新聊天记录**
        session["conversation_history"].append({"role": "assistant", "content": bot_reply})

        return jsonify({"reply": bot_reply})

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500



### ========================== 6️⃣ 清除聊天历史 ========================== ###

@app.route('/api/clear', methods=['POST'])
def clear_chat():
    """
    清除用户聊天记录
    """
    session.pop("conversation_history", None)
    return jsonify({"message": "Chat history cleared"})


### ========================== 7️⃣ 启动 Flask 服务器 ========================== ###

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
