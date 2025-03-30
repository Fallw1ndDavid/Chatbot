import os
import requests
import json
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
from openai import OpenAI
import inspect
import re
from dotenv import load_dotenv
from transformers import pipeline

# Load environment variables
load_dotenv()

# Initialize Flask
app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_default_secret_key")  # Used for session authentication

# Initialize OpenAI API
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# Access password
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "hanliangdeng")  # password

# API Keys
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")  # OpenWeather API Key
NEWS_API_KEY = os.environ["NEWS_API_KEY"]

# Limit the length of the conversation history
MAX_HISTORY = 20

# File for storing chat history
CHAT_HISTORY_FILE = "chat_history.json"

# Load Hugging Face pre-trained sentiment analysis model
sentiment_pipeline = pipeline("sentiment-analysis", model="distilbert/distilbert-base-uncased-finetuned-sst-2-english")


def analyze_sentiment(text):
    """ Use Hugging Face for sentiment analysis """
    result = sentiment_pipeline(text)
    return result[0]["label"], result[0]["score"]  # return sentiment and confidence


### ========================== 1. Login & Log out ========================== ###

@app.route('/')
def index():
    return render_template('login.html')  # Render the login page


@app.route('/login', methods=['POST'])
def login():
    password = request.form.get('password')
    if password == ACCESS_TOKEN:
        session["authenticated"] = True  # Set user as logged in
        return redirect(url_for('chat_page'))
    else:
        return render_template('login.html', error="Invalid password")


@app.route('/logout', methods=['POST'])
def logout():
    session.pop("authenticated", None)
    return redirect(url_for('index'))


### ========================== 2. Chat Page ========================== ###

@app.route('/chat')
def chat_page():
    if not session.get("authenticated"):
        return redirect(url_for('index'))  # Redirect unauthenticated users to the login page
    return render_template('chat.html')


# ========================== 3. Chat management API ========================== #
def load_chat_history():
    """ Load chat history from a JSON file """
    if os.path.exists(CHAT_HISTORY_FILE):
        with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as file:
            return json.load(file)
    return {}


def save_chat_history(history):
    """ Save chat history to a JSON file """
    with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as file:
        json.dump(history, file, ensure_ascii=False, indent=4)


@app.route('/api/get_chats', methods=['GET'])
def get_chats():
    """ Retrieve all chat history """
    history = load_chat_history()
    chat_list = [{"id": chat_id, "title": chat["title"]} for chat_id, chat in history.items()]
    return jsonify(chat_list)


@app.route('/api/get_chat/<chat_id>', methods=['GET'])
def get_chat(chat_id):
    """ Retrieve specific chat content """
    history = load_chat_history()
    if chat_id in history:
        return jsonify({"messages": history[chat_id]["messages"]})
    return jsonify({"error": "Chat not found"}), 404


@app.route('/api/delete_chat/<chat_id>', methods=['DELETE'])
def delete_chat(chat_id):
    """ Delete the chat """
    history = load_chat_history()
    if chat_id in history:
        del history[chat_id]
        save_chat_history(history)
        return jsonify({"message": "Chat deleted successfully"})
    return jsonify({"error": "Chat not found"}), 404


@app.route('/api/rename_chat/<chat_id>', methods=['POST'])
def rename_chat(chat_id):
    """ Rename the chat """
    history = load_chat_history()
    data = request.json
    new_title = data.get("title")

    if chat_id in history and new_title:
        history[chat_id]["title"] = new_title
        save_chat_history(history)
        return jsonify({"message": "Chat renamed successfully"})
    return jsonify({"error": "Chat not found or invalid title"}), 400


### ========================== 4. Real-time Weather Query (based on OpenWeather API) ========================== ###

def query_openweather_function(city="Beijing", units="metric", language="zh_cn",
                               api_key=None, ):
    """
    Use the OpenWeather API to retrieve real-time weather information for a specified city, and return the result as a JSON-formatted string.

    Parameters:
    city (str): Required. The city for which to query the weather. Default is "beijing". If the input is a Chinese name of a city in China, convert it to its corresponding English name (e.g., “北京市” should be input as "beijing").
    units (str): Units of measurement, default is "metric" (Celsius).
    language (str): Language of the output information, default is "zh_cn" (Simplified Chinese).
    api_key (str): API key used to access the OpenWeather API.

    Returns:
    str: The retrieved weather information in a JSON-formatted string. If the query fails, a JSON-formatted string containing the error message will be returned.
    """

    api_key = os.getenv("OPENWEATHER_API_KEY")

    if not api_key:
        print("OpenWeatherAPI Key not set or invalid")
        return json.dumps({"error": "OpenWeatherAPI Key is missing or invalid."})

    # Build the request URL
    url = "https://api.openweathermap.org/data/2.5/weather"

    # Set query parameters
    params = {
        "q": city,
        "appid": api_key,
        "units": units,
        "lang": language
    }

    # Send a GET request
    response = requests.get(url, params=params)

    # Check the response status
    if response.status_code == 200:
        # Parse the response data
        data = response.json()
        print("✅ OpenWeather API Response:", data)  # Print the data returned by the API

        # Convert the result to a JSON-formatted string
        return json.dumps(data)
    else:
        # create an error message
        error_message = {
            "Error": f"Query failed, Status Code：{response.status_code}",
            "Response data": response.text
        }

        print("OpenWeather API Error:", error_message)
        # Convert error messages to JSON-formatted strings
        return json.dumps(error_message)


### ========================== 5. Real-time news query (based on NewsAPI) ========================== ###
def query_news_function(topic="technology", language="zh", page_size=5, api_key=None):
    """
    Use NewsAPI to query the latest news on a specified topic, limiting the number of returned news items.

    Parameters:
    - topic (str): The topic of the news to query, default is "technology".
    - language (str): The language of the news, default is "zh" (Simplified Chinese).
    - page_size (int): The number of news items to return, default is 5.
    - api_key (str): The API key for NewsAPI.

    Returns:
    - str: The retrieved news information, returned in HTML format (for optimized display).
    """

    api_key = os.getenv("NEWS_API_KEY")

    if not api_key:
        print("NewsAPI Key not set or invalid")
        return json.dumps({"error": "NewsAPI Key is missing or invalid."})

    url = "https://newsapi.org/v2/everything"

    params = {
        "q": topic,
        "language": language,
        "pageSize": page_size,  # Limit the number of returned items
        "apiKey": api_key
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        articles = data.get("articles", [])

        # Retrieve up to 10 news items only
        articles = articles[:10]

        # Generate in Markdown format
        news_summary = "\n\n".join([
            f"**[{article.get('title', '无标题')}]({article.get('url', '#')})**  \n来源: {article['source'].get('name', '未知来源')}"
            for article in articles
        ])

        return json.dumps({"summary": news_summary})

    else:
        return json.dumps({
            "error": f"Query failed, Status Code：{response.status_code}",
            "response": response.text
        })


### ========================== 6. OpenAI Function Calling ========================== ###

class AutoFunctionGenerator:
    """
    The AutoFunctionGenerator class is used to automatically generate JSON Schema descriptions for a series of functional functions.
    This class utilizes the OpenAI API and adopts a Few-shot learning approach to generate these descriptions.

    Attributes:
    - functions_list (list): A list containing multiple functional functions.
    - max_attempts (int): The maximum number of attempts, used to handle API call failures.

    Methods:
    - __init__ : Initializes the AutoFunctionGenerator class.
    - generate_function_descriptions : Automatically generates JSON Schema descriptions for the functional functions.
    - _call_openai_api : Calls the OpenAI API.
    - auto_generate : Automatically generates JSON Schema descriptions for the functional functions and handles any exceptions.
    """

    def __init__(self, functions_list, max_attempts=3):
        """
        Initialize the AutoFunctionGenerator class.

        参数:
        - functions_list (list): A list containing multiple functional functions.
        - max_attempts (int): The maximum number of attempts.
        """
        self.functions_list = functions_list
        self.max_attempts = max_attempts

    def generate_function_descriptions(self):
        """
        Automatically generate JSON Schema descriptions for functional functions.

        Returns:
        - list: A list containing the JSON Schema descriptions.
        """
        # Create an empty list to store the JSON Schema description for each functional function
        functions = []

        for function in self.functions_list:
            # Read the docstring of the specified function
            function_description = inspect.getdoc(function)

            # Read the function name of the target function
            function_name = function.__name__

            # Define Few-shot prompt for the system role
            system_Q = "你是一位优秀的数据分析师，现在有一个函数的详细声明如下：%s" % function_description
            system_A = "计算年龄总和的函数，该函数从一个特定格式的JSON字符串中解析出DataFrame，然后计算所有人的年龄总和并以JSON格式返回结果。\
                        \n:param input_json: 必要参数，要求字符串类型，表示含有个体年龄数据的JSON格式字符串 \
                        \n:return: 计算完成后的所有人年龄总和，返回结果为JSON字符串类型对象"

            # Define Few-shot prompt for the user role
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

            # Define input

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
                print("Error: API returned None")
                return []

            if not hasattr(response, "choices") or not response.choices:
                print("Error: No choices field in the API response")
                return []

            if not response or not response.choices:
                print("Error: OpenAI API returned an empty response")
                continue

            content = response.choices[0].message.content.strip()

            if not content:
                print("Error: OpenAI API returned an empty response")
                continue

            try:
                # **Remove Markdown code blocks** (to prevent json.loads() from failing)
                cleaned_content = re.sub(r"^```json\n|\n```$", "", content)

                print("🔵 Parsed JSON Schema:", cleaned_content)

                schema_json = json.loads(cleaned_content)  # parse JSON

                if function_name in ["query_news_function", "query_openweather_function"]:
                    if "parameters" in schema_json and "properties" in schema_json["parameters"]:
                        schema_json["parameters"]["properties"].pop("api_key", None)
                        schema_json["parameters"]["required"] = [
                            param for param in schema_json["parameters"]["required"] if param != "api_key"
                        ]

                functions.append(schema_json)

            except json.JSONDecodeError as e:
                print(f"JSONDecodeError: {e}")
                print(f"API response content: {content}")  # print API response
                continue

        return functions

    def _call_openai_api(self, messages):
        """
        Private method used to call the OpenAI API.

        Parameters:
        - messages (list): A list of messages containing the information required by the API.

        Returns:
        - object: The response object from the API call.
        """

        return client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
        )

    def auto_generate(self):
        """
        Automatically generate JSON Schema descriptions for function definitions and handle any exceptions.

        Returns:
        - list: A list containing the JSON Schema descriptions.

        Exceptions:
        - An exception will be raised if the maximum number of attempts is reached.
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


### ========================== 7. GPT-4o Chatbot ========================== ###
def generate_chat_title(first_message):
    """
    Have GPT-4o generate a brief conversation topic based on the first sentence.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system",
                 "content": "Summarize the following user input into a short conversation title. If the input is entirely in English, generate an English title. If it includes another language, generate the title in that language, with a maximum of 24 characters."},
                {"role": "user", "content": first_message}
            ],
            temperature=0.3,  # Reduce randomness to ensure title stability
            max_tokens=10,  # Limit the length of the generated title
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"Failed to generate chat title: {e}")
        return first_message[:20]  # Use the first 20 characters of the first sentence in case of failure


@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        if not session.get("authenticated"):
            return jsonify({"error": "Unauthorized access"}), 401  # Unauthorized users are denied access

        data = request.json
        user_input = data.get('message', '').strip()
        chat_id = data.get('chat_id')

        if not user_input:
            return jsonify({"error": "Message cannot be empty"}), 400

        # **Perform sentiment analysis**
        sentiment, confidence = analyze_sentiment(user_input)
        print(f"User Sentiment: {sentiment}, Confidence: {confidence:.2f}")  # print the result of sentiment analysis

        # Load chat history
        history = load_chat_history()
        if chat_id not in history:
            history[chat_id] = {
                "title": generate_chat_title(user_input),  # Use GPT to generate the title
                "messages": []
            }

        # Add user messages to history
        history[chat_id]["messages"].append({"role": "user", "content": user_input})

        # **Adding sentiment analysis influence during GPT invocation**
        system_messages = []
        if sentiment == "NEGATIVE" and confidence > 0.75:
            system_messages.append({"role": "system",
                                    "content": "The user may be feeling down; please try to respond with comfort and encouragement."})
        elif sentiment == "POSITIVE":
            system_messages.append({"role": "system",
                                    "content": "The user is in a great mood; please respond in a more enthusiastic and lively manner!"})

        # parse Function Calling
        function_list = [query_openweather_function,
                         query_news_function]  # External functions that require GPT-4o to call
        generator = AutoFunctionGenerator(function_list)  # generate JSON Schema
        functions = generator.auto_generate()
        print("Generated function descriptions:", functions)

        # **Check if functions is empty**
        if not functions:
            return jsonify({"error": "Function descriptions are empty."}), 500

        # **The first call to GPT-4o**
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=history[chat_id]["messages"] + system_messages,
            functions=functions,
            function_call="auto"
        )

        # **Print OpenAI API Responses**
        print("🟢 OpenAI API Response:", response)

        response_message = response.choices[0].message

        # **Check if an external function needs to be called**
        if response_message.function_call:
            function_name = response_message.function_call.name
            function_args = json.loads(response_message.function_call.arguments)

            print(f"✅ Trigger Function Calling: {function_name}，Arguments: {function_args}")

            if function_name == "query_news_function" and "api_key" not in function_args:
                function_args["api_key"] = os.getenv("NEWS_API_KEY")
            if function_name == "query_openweather_function" and "api_key" not in function_args:
                function_args["api_key"] = os.getenv("OPENWEATHER_API_KEY")

            # **Call different APIs**
            if function_name == "query_openweather_function":
                function_response = query_openweather_function(**function_args)
            elif function_name == "query_news_function":
                function_response = query_news_function(**function_args)
            else:
                function_response = json.dumps({"error": f"Unknown Function: {function_name}"})

            # **Parse the API response**
            try:
                function_response_data = json.loads(function_response)
                if isinstance(function_response_data, dict) and "summary" in function_response_data:
                    function_response = function_response_data["summary"]
                elif isinstance(function_response_data, dict):
                    function_response = json.dumps(function_response_data, ensure_ascii=False, indent=2)
            except json.JSONDecodeError:
                pass

            # **The second call to GPT-4o, let it process the return value of the function call**
            second_response = client.chat.completions.create(
                model="gpt-4o",
                messages=history[chat_id]["messages"] + [
                    {"role": "function", "name": function_name, "content": function_response}
                ]
            )

            bot_reply = second_response.choices[0].message.content
        else:
            print("❌ OpenAI did not trigger Function Calling, returned standard chat content")
            bot_reply = response_message.content

        # **Update chat history**
        history[chat_id]["messages"].append({
            "role": "assistant",
            "content": bot_reply,
            "sentiment": sentiment,
            "confidence": confidence
        })

        # *Store chat history**
        save_chat_history(history)

        return jsonify({"reply": bot_reply, "sentiment": sentiment, "confidence": confidence})

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


### ========================== 8. Clear chat history ========================== ###

@app.route('/api/clear', methods=['POST'])
def clear_chat():
    """
    Clear user chat history
    """
    session.pop("conversation_history", None)
    return jsonify({"message": "Chat history cleared"})


### ==========================  9. Start the Flask server ========================== ###

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True, threaded=True)
