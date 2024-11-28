from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import openai

app = Flask(__name__)
CORS(app)  # 允许跨域请求

# 设置 OpenAI API Key
openai.api_key = "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"

# 默认页面
@app.route('/')
def index():
    return render_template('index.html')

# Chat API 路由
@app.route('/api/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message', '')

    # 构建 GPT-4 请求
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": user_input},
        ]
    )

    # 获取 GPT-4 的回复
    bot_reply = response['choices'][0]['message']['content']
    return jsonify({"reply": bot_reply})


# 添加对话历史记录
conversation_history = [{"role": "system", "content": "You are a helpful assistant."}]


@app.route('/api/chat', methods=['POST'])
def chat():
    user_input = request.json.get('message', '')
    conversation_history.append({"role": "user", "content": user_input})

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=conversation_history
    )

    bot_reply = response['choices'][0]['message']['content']
    conversation_history.append({"role": "assistant", "content": bot_reply})
    return jsonify({"reply": bot_reply})


if __name__ == '__main__':
    app.run(debug=True)

