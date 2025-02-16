import os
import requests
from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
from transformers import pipeline
from openai import OpenAI

# 初始化 Flask
app = Flask(__name__)
CORS(app)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_default_secret_key")  # 用于 Session 认证

# OpenAI API 初始化
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

# 限制对话历史长度
MAX_HISTORY = 10

# 访问密码
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", "hanliangdeng")  # 默认密码

# API Keys
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")  # OpenWeather API Key
NEWS_API_KEY = os.getenv("NEWS_API_KEY")  # NewsAPI Key

# 加载 Hugging Face 预训练情感分析模型
sentiment_analyzer = pipeline("sentiment-analysis")


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


### ========================== 3️⃣ 情感分析（Sentiment Analysis） ========================== ###

def analyze_sentiment(text):
    """
    解析用户输入的情感（POSITIVE, NEGATIVE, NEUTRAL）
    """
    result = sentiment_analyzer(text)[0]  # 获取预测结果
    return result['label']


### ========================== 4️⃣ 实时数据查询（Weather & News） ========================== ###

def get_weather(city):
    """
    获取实时天气数据
    """
    try:
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={OPENWEATHER_API_KEY}&units=metric"
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200:
            return f"The current temperature in {city} is {data['main']['temp']}°C with {data['weather'][0]['description']}."
        else:
            return "Sorry, I couldn't retrieve the weather data."
    except Exception as e:
        return f"Error retrieving weather: {str(e)}"


def get_news(topic):
    """
    获取最新新闻
    """
    try:
        url = f"https://newsapi.org/v2/everything?q={topic}&apiKey={NEWS_API_KEY}&language=en&pageSize=3"
        response = requests.get(url)
        data = response.json()
        if response.status_code == 200 and "articles" in data:
            articles = data["articles"][:3]  # 取最新的 3 篇新闻
            news_list = "\n".join([f"{idx + 1}. {art['title']} - {art['url']}" for idx, art in enumerate(articles)])
            return f"Here are the latest news about {topic}:\n{news_list}"
        else:
            return "Sorry, I couldn't retrieve news for that topic."
    except Exception as e:
        return f"Error retrieving news: {str(e)}"


### ========================== 5️⃣ GPT-4o Chatbot（支持记忆 & 实时数据） ========================== ###

@app.route('/api/chat', methods=['POST'])
def chat():
    try:
        if not session.get("authenticated"):
            return jsonify({"error": "Unauthorized access"}), 401  # 未授权用户禁止访问

        user_input = request.json.get('message', '').strip()
        if not user_input:
            return jsonify({"error": "Message cannot be empty"}), 400

        # 检测天气查询
        if "weather" in user_input.lower():
            city = user_input.split("in")[-1].strip()
            weather_info = get_weather(city)
            return jsonify({"reply": weather_info})

        # 检测新闻查询
        if "news" in user_input.lower():
            topic = user_input.split("about")[-1].strip()
            news_info = get_news(topic)
            return jsonify({"reply": news_info})

        # 进行情感分析
        sentiment = analyze_sentiment(user_input)

        # 根据情感调整 GPT 的系统提示
        if sentiment == "NEGATIVE":
            system_message = "You are a kind and empathetic assistant. Provide comforting and supportive responses."
        elif sentiment == "POSITIVE":
            system_message = "You are a cheerful assistant. Keep up the positive energy!"
        else:
            system_message = "You are a helpful AI assistant."

        # 初始化对话历史
        if "conversation_history" not in session:
            session["conversation_history"] = [{"role": "system", "content": system_message}]

        # 追加用户输入
        session["conversation_history"].append({"role": "user", "content": user_input})

        # 限制对话历史长度
        session["conversation_history"] = session["conversation_history"][-MAX_HISTORY:]

        # 调用 OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=session["conversation_history"]
        )

        bot_reply = response.choices[0].message.content.strip()

        # 记录 GPT 的回答
        session["conversation_history"].append({"role": "assistant", "content": bot_reply})

        return jsonify({"reply": bot_reply, "sentiment": sentiment})

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


### ========================== 6️⃣ 清除聊天历史 ========================== ###

@app.route('/api/clear', methods=['POST'])
def clear_chat():
    """
    清除用户聊天记录
    """
    if "conversation_history" in session:
        session.pop("conversation_history")
    return jsonify({"message": "Chat history cleared"})


### ========================== 7️⃣ 启动 Flask 服务器 ========================== ###

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
