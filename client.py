import requests
import os

class OpenEnvClient:
    def __init__(self, base_url=None):
        # Hugging Face default port 7860 ya local environment
        self.base_url = base_url or os.getenv("OPENENV_URL", "http://localhost:7860")

    def reset(self):
        """Tere app.py mein /reset endpoint hai"""
        response = requests.post(f"{self.base_url}/reset")
        return response.json()

    def step(self, action):
        """Tere app.py mein /step endpoint ActionRequest (json) leta hai"""
        response = requests.post(f"{self.base_url}/step", json={"action": int(action)})
        return response.json()

    def get_state(self):
        """Tere app.py mein /state endpoint hai"""
        response = requests.get(f"{self.base_url}/state")
        return response.json()

    def get_tasks(self):
        """Tere app.py mein /tasks endpoint hai"""
        response = requests.get(f"{self.base_url}/tasks")
        return response.json()