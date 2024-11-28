import os
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
import openai
from uuid import uuid4

# 创建 Flask 应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 设置 Flask 的密钥，用于会话管理
app.secret_key = "abcd123"

# 设置 OpenAI API Key（从环境变量获取）
openai.api_key = os.getenv("OPENAI_API_KEY")

# 默认页面路由
@app.route('/')
def index():
    return render_template('index.html')  # 确保 templates 文件夹中有 index.html 文件

# 会话初始化，用于区分用户的对话历史
@app.before_request
def initialize_session():
    if "session_id" not in session:
        session["session_id"] = str(uuid4())
    if "conversation_history" not in session:
        session["conversation_history"] = [{"role": "system", "content": "You are a helpful assistant."}]

# 聊天接口路由
@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        # 获取用户输入
        user_input = request.json.get('message', '')
        if not user_input.strip():
            return jsonify({"error": "Message cannot be empty"}), 400

        # 获取用户会话的对话历史
        conversation_history = session["conversation_history"]

        # 添加用户消息到对话历史
        conversation_history.append({"role": "user", "content": user_input})

        # 调用 OpenAI ChatCompletion 接口
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",  # 如果有 GPT-4 权限，可以改为 "gpt-4"
            messages=conversation_history
        )

        # 提取 OpenAI 回复
        bot_reply = response['choices'][0]['message']['content']
        conversation_history.append({"role": "assistant", "content": bot_reply})

        # 更新会话中的对话历史
        session["conversation_history"] = conversation_history

        return jsonify({"reply": bot_reply})

    except openai.error.AuthenticationError:
        return jsonify({"error": "Invalid OpenAI API Key. Please check your configuration."}), 401
    except openai.error.OpenAIError as e:
        return jsonify({"error": f"OpenAI API error: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500

# 主程序入口
if __name__ == '__main__':
    # Render 部署需要动态端口
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
