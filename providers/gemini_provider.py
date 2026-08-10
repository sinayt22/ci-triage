import os
from google import genai
from google.genai import types
from base import LLMProvider

DEFAULT_MODEL = 'gemini-3.5-flash-lite'

class GeminiProvider(LLMProvider):
    def __init__(self, model: str = DEFAULT_MODEL):
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set")
        self.client = genai.Client(api_key=api_key)
        self.model = self.model

    def complete(self, system: str, user: str, temperature: float = 0, max_tokens: int = 200) -> str:
        response = self.client.models.generate_content(
            model = self.model,
            contents = user,
            config = types.GenerateContentConfig(
                system_instructions=system,
                temperature=temperature,
                max_output_tokens=max_tokens
            ),
        )
        return response.text