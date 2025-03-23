from locust import HttpUser, task, between

class ChatbotLoadTest(HttpUser):
    wait_time = between(1, 3)  # Each user request is spaced 1 to 3 seconds apart

    def on_start(self):
        """ Each user must log in upon startup to obtain a Session """
        response = self.client.post("/login", data={"password": "hanliangdeng"})
        print(f"Login response: {response.status_code}, {response.text}")

    @task
    def test_chat(self):
        """Simulate a user sending a message"""
        self.client.post("/api/chat", json={"message": "Could you please explain to me in detail what natural language processing is?", "chat_id": "test_chat"})

    @task
    def test_news_request(self):
        """Simulate querying the news API"""
        self.client.post("/api/chat", json={"message": "Give me the latest three news items.", "chat_id": "test_chat"})

    @task
    def test_weather_request(self):
        """Simulate querying the weather API"""
        self.client.post("/api/chat", json={"message": "How is the weather in Shanghai?", "chat_id": "test_chat"})

if __name__ == "__main__":
    import os
    os.system("locust -f locust_test.py --host=http://127.0.0.1:5000")
