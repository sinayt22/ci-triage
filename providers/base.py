from abc import ABC, abstractmethod

class LLMProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, temperature: float = 0, max_tokens: int = 200) -> str:
        raise NotImplementedError


    