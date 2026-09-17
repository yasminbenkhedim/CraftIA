from typing import Dict, Any, Optional
from app.services.llm.base import BaseLLMProvider
from app.services.llm.groq import GroqProvider

class LLMService:
    """
    Unified LLM Service interface decoupling agent execution from specific LLM providers.
    """

    _provider: BaseLLMProvider = GroqProvider()

    @classmethod
    def set_provider(cls, provider: BaseLLMProvider):
        cls._provider = provider

    @classmethod
    def generate_json(cls, prompt: str, system_prompt: str, fallback_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executes structured JSON generation using the active LLM provider.
        """
        return cls._provider.generate_json(prompt, system_prompt, fallback_dict)

    @classmethod
    def generate_json_advanced(cls, prompt: str, system_prompt: str, fallback_dict: Dict[str, Any], temperature: float = 0.7, timeout: float = 25.0) -> Dict[str, Any]:
        """
        Executes advanced structured JSON generation supporting temperature and timeout.
        """
        return cls._provider.generate_json_advanced(prompt, system_prompt, fallback_dict, temperature=temperature, timeout=timeout)

    # Short enough that a slow provider cannot visibly stall job creation, which calls
    # generate_job_title on the request path.
    JOB_TITLE_TIMEOUT_SEC = 6.0
    JOB_TITLE_MAX_CHARS = 60

    @classmethod
    def generate_job_title(cls, prompt: str) -> str:
        """
        A 4-6 word display name for a job, e.g. "FitAI Fitness App Demo".

        Always returns a usable string: with no API key, on a timeout, or on a response
        that ignored the format, it falls back to a trimmed form of the prompt. Creating
        a job must never fail because the naming model was unavailable.
        """
        text = (prompt or "").strip()
        if not text:
            return "Untitled deliverable"

        fallback = cls._fallback_job_title(text)
        system_prompt = (
            "You name content-generation jobs. Given the user's prompt, reply with JSON "
            '{"title": "..."} where title is a 4-6 word title-case name for the deliverable. '
            "Name the subject, not the task: no leading verbs like Create/Build/Generate, "
            "no quotes, no trailing punctuation, no file extensions."
        )

        try:
            result = cls.generate_json_advanced(
                f"Prompt:\n{text[:1200]}",
                system_prompt,
                {"title": fallback},
                temperature=0.3,
                timeout=cls.JOB_TITLE_TIMEOUT_SEC,
            )
        except Exception:
            return fallback

        title = result.get("title") if isinstance(result, dict) else None
        return cls._clean_job_title(title) or fallback

    @classmethod
    def _clean_job_title(cls, value: Any) -> Optional[str]:
        """Rejects anything that is not a short, plain title."""
        if not isinstance(value, str):
            return None
        title = " ".join(value.split()).strip().strip('"\'“”').rstrip(".!,;:")
        if not title or len(title) > cls.JOB_TITLE_MAX_CHARS:
            return None
        if len(title.split()) > 9:
            return None   # the model echoed the prompt back instead of naming it
        return title

    @classmethod
    def _fallback_job_title(cls, prompt: str) -> str:
        title = " ".join(prompt.split()[:6]).strip().rstrip(".!,;:")
        if len(title) > cls.JOB_TITLE_MAX_CHARS:
            title = title[:cls.JOB_TITLE_MAX_CHARS].rsplit(" ", 1)[0]
        return title or "Untitled deliverable"
