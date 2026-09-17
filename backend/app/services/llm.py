import json
import urllib.request
import urllib.error
import logging
from typing import Dict, Any
from app.core.config import settings

logger = logging.getLogger("uvicorn")

def _build_api_url() -> str:
    """Build the chat completions URL from OPENAI_BASE_URL."""
    base = settings.OPENAI_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/openai/v1/chat/completions"


class GroqLLMService:
    """
    OpenAI-compatible LLM Service (PwC Azure OpenAI endpoint or Groq).
    Uses OPENAI_BASE_URL + OPENAI_API_KEY / OPENAI_MODEL from environment.
    """

    @classmethod
    def _get_api_url(cls) -> str:
        return _build_api_url()

    @classmethod
    def generate_presentation_structure(cls, prompt: str) -> Dict[str, Any]:
        """
        Queries Groq LLM to generate structured JSON for a presentation deck.
        """
        api_key = settings.GROQ_API_KEY
        if not api_key:
            logger.warning("GROQ_API_KEY is missing. Using fallback content structure.")
            return cls._fallback_presentation_structure(prompt)

        system_prompt = (
            "You are an expert presentation designer and executive speechwriter. "
            "Given a user topic, generate a structured presentation deck JSON payload. "
            "Output MUST be strict raw JSON without markdown codeblock formatting matching this schema:\n"
            "{\n"
            '  "title": "Main Presentation Title",\n'
            '  "subtitle": "Compelling Subtitle Description",\n'
            '  "slides": [\n'
            '    {\n'
            '      "slide_title": "Slide 1 Title",\n'
            '      "subtitle": "Section Subtitle",\n'
            '      "points": ["Bullet point 1", "Bullet point 2", "Bullet point 3"]\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Generate 5 to 7 detailed slides matching the user's prompt."
        )

        user_content = f"Create a high-impact presentation deck for the following requirement: {prompt}"
        return cls._call_groq_json(system_prompt, user_content, cls._fallback_presentation_structure(prompt))

    @classmethod
    def generate_report_structure(cls, prompt: str) -> Dict[str, Any]:
        """
        Queries Groq LLM to generate structured JSON for a multi-section technical report.
        """
        api_key = settings.GROQ_API_KEY
        if not api_key:
            return cls._fallback_report_structure(prompt)

        system_prompt = (
            "You are a senior technical writer and research scientist. "
            "Generate a comprehensive, professional multi-section report JSON structure for a user topic. "
            "Output MUST be strict raw JSON without markdown codeblock formatting matching this schema:\n"
            "{\n"
            '  "title": "Report Title",\n'
            '  "subtitle": "Subtitle or Subject Area",\n'
            '  "abstract": "Comprehensive executive summary and abstract of the report.",\n'
            '  "sections": [\n'
            '    {\n'
            '      "section_title": "1. Introduction & Background",\n'
            '      "content": "Detailed explanatory paragraph...",\n'
            '      "bullets": ["Key point 1", "Key point 2", "Key point 3"]\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Generate at least 4 detailed sections matching the user request."
        )

        user_content = f"Write a comprehensive technical report for the following prompt: {prompt}"
        return cls._call_groq_json(system_prompt, user_content, cls._fallback_report_structure(prompt))

    @classmethod
    def _call_groq_json(cls, system_prompt: str, user_content: str, fallback_dict: Dict[str, Any], temperature: float = 0.7, timeout: float = 25.0) -> Dict[str, Any]:
        api_key = settings.GROQ_API_KEY  # mapped to OPENAI_API_KEY env var
        if not api_key:
            return fallback_dict

        payload = {
            "model": settings.GROQ_MODEL,  # mapped to OPENAI_MODEL env var
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                cls._get_api_url(),
                data=req_data,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}",
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) CreateFlowAI/1.0"
                },
                method="POST"
            )

            with urllib.request.urlopen(req, timeout=timeout) as response:
                resp_body = response.read().decode("utf-8")
                resp_json = json.loads(resp_body)
                content_str = resp_json["choices"][0]["message"]["content"]
                parsed = json.loads(content_str)
                if isinstance(parsed, dict) and "usage" in resp_json:
                    parsed["_llm_meta"] = {
                        "model": resp_json.get("model", settings.GROQ_MODEL),
                        "usage": resp_json.get("usage", {}),
                    }
                return parsed

        except Exception as e:
            logger.error(f"LLM API Error: {e}. Returning fallback structure.")
            return fallback_dict

    @classmethod
    def _fallback_presentation_structure(cls, prompt: str) -> Dict[str, Any]:
        return {
            "title": "CreateFlow AI Presentation",
            "subtitle": f"Generated for: {prompt[:60]}...",
            "slides": [
                {
                    "slide_title": "Executive Overview",
                    "subtitle": "Core Strategy & Vision",
                    "points": [
                        f"Target Goal: {prompt}",
                        "Automated Multi-Agent Pipeline Execution",
                        "High-Impact Visual Layout & Typography"
                    ]
                }
            ]
        }

    @classmethod
    def _fallback_report_structure(cls, prompt: str) -> Dict[str, Any]:
        return {
            "title": "Technical Research & Architecture Report",
            "subtitle": f"Subject: {prompt[:60]}...",
            "abstract": (
                f"This document provides a comprehensive technical overview for the request: '{prompt}'. "
                "The platform leverages a scalable multi-agent framework designed to orchestrate specialized AI "
                "generation pipelines, producing publication-ready deliverables."
            ),
            "sections": [
                {
                    "section_title": "1. System Architecture & Component Design",
                    "content": (
                        "The CreateFlow AI architecture is built on a high-performance FastAPI backend paired with "
                        "isolated agent processing queues. Each agent implements a common interface for validation, "
                        "execution, and artifact compilation."
                    ),
                    "bullets": [
                        "- Modular BaseAgent abstract interface with strict input validation",
                        "- Asynchronous Redis/ARQ task worker pools for non-blocking execution",
                        "- Real-time progress state updates surfaced to the Angular frontend"
                    ]
                },
                {
                    "section_title": "2. Multi-Agent Orchestration & Workflow Lifecycle",
                    "content": (
                        "Requests received by the API layer are validated, recorded in PostgreSQL/SQLite database storage, "
                        "and dispatched to specialized generation agents. The workflow runner handles lifecycle state "
                        "transitions from QUEUED to RUNNING, COMPLETED, or FAILED."
                    ),
                    "bullets": [
                        "- Automated step progress reporting (0% to 100%)",
                        "- Secure artifact storage and authenticated file download serving",
                        "- Groq AI (Llama 3.3 70B) intelligence integration"
                    ]
                }
            ]
        }

    def __init__(self, provider: str = "gemini", model: Optional[str] = None):
        self.provider = provider.lower() if provider else "gemini"
        self.model = model or self._default_model_for_provider(self.provider)

    @classmethod
    def _default_model_for_provider(cls, provider: str) -> str:
        defaults = {
            "gemini": "gemini-1.5-pro",
            "openai": "gpt-4o",
            "anthropic": "claude-3-5-sonnet",
            "ollama": "llama3"
        }
        return defaults.get(provider.lower(), "gemini-1.5-pro")

    @classmethod
    def generate_json(cls, prompt: str, system_prompt: str, fallback_dict: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generic JSON generator helper used by CognitivePlanner, RetentionArchitect, etc.
        """
        return cls._call_groq_json(system_prompt, prompt, fallback_dict or {})

    @classmethod
    def generate_json_advanced(cls, prompt: str, system_prompt: str, fallback_dict: Optional[Dict[str, Any]] = None, temperature: float = 0.7, timeout: float = 25.0) -> Dict[str, Any]:
        """
        Advanced JSON generator supporting custom temperature and timeout.
        """
        return cls._call_groq_json(system_prompt, prompt, fallback_dict or {}, temperature=temperature, timeout=timeout)

    @classmethod
    def generate_content(cls, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Generic text generator helper.
        """
        api_key = settings.GROQ_API_KEY
        if not api_key:
            return f"Mock generated analysis for: {prompt[:100]}"
        
        sys_p = system_prompt or "You are an expert AI assistant."
        res = cls._call_groq_json(sys_p, prompt, {"content": "Fallback text response"})
        return res.get("content", str(res))


# Alias for clean imports across agents
LLMService = GroqLLMService
