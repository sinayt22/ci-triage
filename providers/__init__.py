import os

from dotenv import load_dotenv

load_dotenv()


def get_provider():
    name = os.environ.get("LLM_PROVIDER", "gemini").lower()
    model_override = os.environ.get("LLM_MODEL") or None

    if name == "gemini":
        from gemini_provider import DEFAULT_MODEL, GeminiProvider

        return GeminiProvider(model_override or DEFAULT_MODEL)
    elif name == "anthropic":
        from anthropic_provider import DEFAULT_MODEL, AnthropicProvider

        return AnthropicProvider(model_override or DEFAULT_MODEL)
    elif name == "openrouter":
        from openrouter_provider import DEFAULT_MODEL, OpenRouterProvider

        return OpenRouterProvider(model_override or DEFAULT_MODEL)
    else:
        raise ValueError(
            f"Unknown LLM_PROVIDER '{name}'. Expected one of: gemini, anthropic, operouter"
        )
