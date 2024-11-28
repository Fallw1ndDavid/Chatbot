import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import openai

# 创建 Flask 应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 设置 OpenAI API Key（从环境变量获取）
openai.api_key = os.getenv("OPENAI_API_KEY")

# 默认页面路由
@app.route('/')
def index():
    return render_template('index.html')  # 需要在 templates 文件夹中有 index.html

# 聊天接口路由
conversation_history = [{"role": "system", "content": "You are a helpful assistant."}]

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        # 获取用户输入
        user_input = request.json.get('message', '')
        if not user_input.strip():
            return jsonify({"error": "Message cannot be empty"}), 400

        # 记录用户消息
        conversation_history.append({"role": "user", "content": user_input})

        # 调用 OpenAI 接口
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=conversation_history
        )

        # 提取 GPT-4 回复
        bot_reply = response['choices'][0]['message']['content']
        conversation_history.append({"role": "assistant", "content": bot_reply})

        return jsonify({"reply": bot_reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 主程序入口
if __name__ == '__main__':
    # Render 部署需要动态端口
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
