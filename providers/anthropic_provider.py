import os
from anthropic import Anthropic
from base import LLMProvider

DEFAULT_MODEL = "claude-haiku-4-5-20251001"

class AnthropicProvider(LLMProvider):
    def __init__(self, model:str = DEFAULT_MODEL):
        self.model = model
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise RuntimeError("Missing ANTHROPIC_API_KEY")
        self.client = Anthropic(api_key=api_key)

    def complete(self, system:str, user:str, temperature:float=0, max_tokens:int = 200) -> str:
        response = self.client.message.create(
            model = self.model,
            max_tokens = max_tokens,
            temperature = temperature,
            system = system,
            messages=[{"role": "user", "content": user}]
        )
        return response.content[0].text
        
