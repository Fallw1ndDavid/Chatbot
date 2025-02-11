import os
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
from openai import OpenAI

# 初始化 Flask 应用
app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_default_secret_key")  # Flask 会话密钥

# 初始化 OpenAI 客户端
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 设置访问密码
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "hanliangdeng")  # 默认密码

# 限制对话历史长度，防止 Token 过载
MAX_HISTORY = 10  # 仅保留最近 10 轮对话


# 1.登录页面
@app.route('/')
def index():
    return render_template('login.html')  # 渲染登录页面


# 2.登录验证
@app.route('/login', methods=['POST'])
def login():
    password = request.form.get('password')
    if password == ACCESS_TOKEN:
        session["authenticated"] = True  # 设置用户已登录
        return redirect(url_for('chat_page'))
    else:
        return render_template('login.html', error="Invalid password")


# 3.聊天页面
@app.route('/chat')
def chat_page():
    if not session.get("authenticated"):
        return redirect(url_for('index'))  # 未登录用户重定向回登录页
    return render_template('chat.html')


# 4.聊天 API（支持上下文记忆）
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        if not session.get("authenticated"):
            return jsonify({"error": "Unauthorized access"}), 401  # 未授权用户禁止访问

        user_input = request.json.get('message', '').strip()
        if not user_input:
            return jsonify({"error": "Message cannot be empty"}), 400

        # 初始化对话历史（如果 session 中不存在）
        if "conversation_history" not in session:
            session["conversation_history"] = [{"role": "system", "content": "You are a helpful AI assistant."}]

        # 追加用户输入
        session["conversation_history"].append({"role": "user", "content": user_input})

        # 限制对话历史长度
        session["conversation_history"] = session["conversation_history"][-MAX_HISTORY:]

        # 调用 OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=session["conversation_history"]
        )

        # 提取 GPT 回复
        bot_reply = response.choices[0].message.content.strip()

        # 记录 GPT 的回答
        session["conversation_history"].append({"role": "assistant", "content": bot_reply})

        return jsonify({"reply": bot_reply})

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


# 5.清除对话历史
@app.route('/api/clear', methods=['POST'])
def clear_chat():
    if "conversation_history" in session:
        session.pop("conversation_history")  # 清除会话记录
    return jsonify({"message": "Chat history cleared"})


# 6.退出登录
@app.route('/logout', methods=['POST'])
def logout():
    session.pop("authenticated", None)
    return redirect(url_for('index'))


# 7.运行 Flask 服务器
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
