from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseLLMProvider(ABC):
    """
    Abstract interface for LLM providers (Groq, OpenAI, Gemini, etc.).
    """

    @abstractmethod
    def generate_json(self, prompt: str, system_prompt: str, fallback_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates structured JSON from the LLM provider.
        """
        pass

    def generate_json_advanced(self, prompt: str, system_prompt: str, fallback_dict: Dict[str, Any], temperature: float = 0.7, timeout: float = 25.0) -> Dict[str, Any]:
        """
        Advanced JSON generator supporting custom temperature and timeout.
        """
        return self.generate_json(prompt, system_prompt, fallback_dict)
