import os
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from openai import OpenAI

# 初始化 Flask 应用
app = Flask(__name__)
CORS(app)

# 初始化 OpenAI 客户端
client = OpenAI(
    api_key=os.environ.get("OPENAI_API_KEY")  # 从环境变量获取 API Key
)

# 默认页面路由
@app.route('/')
def index():
    return render_template('index.html')  # 确保 templates 文件夹中有 index.html 文件

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
        bot_reply = response["choices"][0]["message"]["content"]

        return jsonify({"reply": bot_reply})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 主程序入口
if __name__ == '__main__':
    # 动态端口支持
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
