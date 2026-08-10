import os
from openai import OpenAI
from base import LLMProvider

DEFAULT_MODEL = "google/gemini-2.5-flash-lite"

class OpenRouterProvider(LLMProvider):
    def __init__(self, model:str = DEFAULT_MODEL):
        self.model = model
        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        self.client = OpenAI(api_key=api_key)

    def complete(self, system, user, temperature = 0, max_tokens = 200):
        response = self.client.chat.completions.create(
            model=self.model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user}
            ],
            temperature=temperature
        )

        return response.choices[0].message.content