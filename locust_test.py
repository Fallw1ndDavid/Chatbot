from locust import HttpUser, task, between

class ChatbotLoadTest(HttpUser):
    wait_time = between(1, 3)  # 每个用户请求间隔 1~3 秒

    def on_start(self):
        """ 每个用户启动时先登录，获取 Session """
        response = self.client.post("/login", data={"password": "hanliangdeng"})  # 你的 ACCESS_TOKEN
        print(f"登录响应: {response.status_code}, {response.text}")

    @task
    def test_chat(self):
        """模拟用户发送消息"""
        self.client.post("/api/chat", json={"message": "今天天气如何？", "chat_id": "test_chat"})

    @task
    def test_long_message(self):
        """测试超长文本输入"""
        long_message = "天气" * 500  # 500 个"天气"字符
        self.client.post("/api/chat", json={"message": long_message, "chat_id": "test_chat"})

    @task
    def test_empty_message(self):
        """测试空输入"""
        self.client.post("/api/chat", json={"message": "", "chat_id": "test_chat"})

    @task
    def test_news_request(self):
        """模拟查询新闻 API"""
        self.client.post("/api/chat", json={"message": "给我最新的三条新闻", "chat_id": "test_chat"})

    @task
    def test_weather_request(self):
        """模拟查询天气 API"""
        self.client.post("/api/chat", json={"message": "上海天气怎么样？", "chat_id": "test_chat"})

if __name__ == "__main__":
    import os
    os.system("locust -f locust_test.py --host=http://127.0.0.1:5000")
