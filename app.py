import os
from flask import Flask, request, jsonify, render_template, redirect, url_for
from flask_cors import CORS
from openai import OpenAI

# 初始化 Flask 应用
app = Flask(__name__)
CORS(app)

# 初始化 OpenAI 客户端
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")  # 从环境变量获取 API Key
)

# 设置访问密码
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "hanliangdeng")  # 默认密码


# 登录页面路由
@app.route('/')
def index():
    return render_template('login.html')  # 渲染登录页面

# 登录验证路由
@app.route('/login', methods=['POST'])
def login():
    password = request.form.get('password')
    if password == ACCESS_TOKEN:
        # 登录成功，重定向到聊天页面
        return redirect(url_for('chat_page'))
    else:
        # 登录失败，返回错误消息
        return render_template('login.html', error="Invalid password")

# 聊天页面路由
@app.route('/chat')
def chat_page():
    return render_template('chat.html')  # 渲染聊天页面

# 聊天接口路由
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        # 获取用户输入
        user_input = request.json.get('message', '')
        if not user_input.strip():
            return jsonify({"error": "Message cannot be empty"}), 400

        # 调用 OpenAI Chat Completion 接口
        response = client.chat.completions.create(
            messages=[
                {"role": "user", "content": user_input}
            ],
            model="gpt-4o",  # 替换为你有权限的模型名称
        )

        # 提取 GPT 的回复
        # 如果 response 对象不支持下标访问，请改用 .to_dict() 或直接通过属性访问
        response_dict = response.to_dict()  # 转换为字典
        bot_reply = response_dict["choices"][0]["message"]["content"]

        return jsonify({"reply": bot_reply})

    except Exception as e:
        # 返回详细错误信息用于调试
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

# 主程序入口
if __name__ == '__main__':
    # 动态端口支持，适用于部署在平台（如 Render）
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
