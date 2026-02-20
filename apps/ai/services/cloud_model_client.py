# apps/ai_bridge/services/cloud_model_client.py
import openai

class CloudModelClient:

    def __init__(self):
        openai.api_key = "YOUR_OPENAI_KEY"

    def generate(self, prompt, task_type="diagnosis"):
        # Example OpenAI GPT-4 call
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return response.choices[0].message.content