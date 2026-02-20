# apps/ai_bridge/services/ai_service.py
from apps.ai.services.local_model_client import LocalModelClient
from apps.ai.services.cloud_model_client import CloudModelClient
from apps.core.utils import is_connected

class AIService:

    def __init__(self):
        self.local_model = LocalModelClient()
        self.cloud_model = CloudModelClient()

    def run_model(self, prompt, task_type="diagnosis"):
        if is_connected():
            # Use cloud model
            return self.cloud_model.generate(prompt, task_type)
        else:
            # Use lightweight local model
            return self.local_model.generate(prompt, task_type)