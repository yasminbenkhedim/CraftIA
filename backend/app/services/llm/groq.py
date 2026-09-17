import json
import urllib.request
import urllib.error
import logging
from typing import Dict, Any, Optional
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider

logger = logging.getLogger("uvicorn")


def _resolve_groq_api_url() -> str:
    """
    Builds the chat-completions URL from settings.OPENAI_BASE_URL (i.e. from .env),
    rather than a hardcoded literal -- so a change to OPENAI_BASE_URL is actually
    respected, and what's logged before each call reflects the real configured value.
    """
    base = (settings.OPENAI_BASE_URL or "https://api.groq.com").rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/openai/v1/chat/completions"


class GroqProvider(BaseLLMProvider):
    """
    Groq LLM Provider — utilise l'API Groq (gratuite) au lieu de Azure PwC.
    Lit GROQ_API_KEY, GROQ_MODEL et OPENAI_BASE_URL depuis le fichier .env
    """

    @property
    def API_URL(self) -> str:
        return _resolve_groq_api_url()

    def generate_json(self, prompt: str, system_prompt: str, fallback_dict: Dict[str, Any]) -> Dict[str, Any]:
        return self.generate_json_advanced(prompt, system_prompt, fallback_dict, temperature=0.7, timeout=30.0)

    def generate_json_advanced(self, prompt: str, system_prompt: str, fallback_dict: Dict[str, Any], temperature: float = 0.7, timeout: float = 30.0) -> Dict[str, Any]:
        api_key = settings.GROQ_API_KEY
        if not api_key:
            logger.warning("GROQ_API_KEY manquant dans .env — utilisation du fallback.")
            return fallback_dict

        model = getattr(settings, "GROQ_MODEL", "llama-3.3-70b-versatile")

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "response_format": {"type": "json_object"}
        }

        api_url = self.API_URL
        key_prefix = f"{api_key[:7]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
        logger.info(f"GroqProvider: Calling {api_url} (model={model}, key={key_prefix})")

        try:
            req_data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                api_url,
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
                        "model": resp_json.get("model", model),
                        "usage": resp_json.get("usage", {}),
                    }
                return parsed

        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = "<no response body>"
            logger.error(f"Groq API Error: HTTP {e.code} from {api_url} -- response body: {body} — utilisation du fallback.")
            return fallback_dict
        except Exception as e:
            logger.error(f"Groq API Error: {type(e).__name__}: {e} (url={api_url}) — utilisation du fallback.")
            return fallback_dict