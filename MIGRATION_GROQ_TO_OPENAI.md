# 🔄 Guide de Migration LLM — Groq ↔ OpenAI (PwC Azure)

Ce document décrit toutes les modifications apportées pour passer de **Groq AI** à l'endpoint **Azure OpenAI PwC**.  
Fournis ce fichier à ton agent pour revenir à Groq.

---

## 📋 Résumé des fichiers modifiés

| Fichier | Nature du changement |
|---|---|
| `backend/app/core/config.py` | Variables d'env + validation au démarrage |
| `backend/app/services/llm/groq.py` | URL API hardcodée → dynamique |
| `backend/app/services/llm.py` | URL API hardcodée → dynamique |
| `docker-compose.yml` | Variables d'env du service api + worker |
| `.env` | Fichier de configuration local |

---

## 1. `backend/app/core/config.py`

### ✅ État actuel (OpenAI PwC)
```python
# LLM API Key configuration — reads OPENAI_API_KEY from environment (PwC Azure OpenAI endpoint)
# Internal name kept as GROQ_API_KEY to avoid cascading renames across all agents
GROQ_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
GROQ_MODEL: str = os.getenv("OPENAI_MODEL", "azure.gpt-4o-mini")

# OpenAI-compatible base URL (PwC endpoint or standard OpenAI)
OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
```
Et dans la validation :
```python
if not settings.GROQ_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY environment variable is not set. ..."
    )
```

### ⏪ Pour revenir à Groq — remplacer par :
```python
# Groq AI Key configuration — MUST be set via environment variable, no hardcoded fallback
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
```
Et dans la validation :
```python
if not settings.GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY environment variable is not set. "
        "Set it before starting the application: "
        "  export GROQ_API_KEY='your-key-here'  (Linux/Mac)\n"
        "  set GROQ_API_KEY=your-key-here        (Windows)"
    )
```
> ⚠️ Supprimer aussi la ligne `OPENAI_BASE_URL: str = os.getenv(...)`.

---

## 2. `backend/app/services/llm/groq.py`

### ✅ État actuel (OpenAI PwC)
```python
def _build_api_url() -> str:
    """Build the chat completions URL from OPENAI_BASE_URL."""
    base = settings.OPENAI_BASE_URL.rstrip("/")
    # Support both Azure-style (/openai/v1/...) and standard OpenAI (/v1/...)
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/openai/v1/chat/completions"

class GroqProvider(BaseLLMProvider):
    @property
    def API_URL(self) -> str:
        return _build_api_url()
    # ... utilise self.API_URL au lieu de self.GROQ_API_URL
```

### ⏪ Pour revenir à Groq — remplacer par :
```python
class GroqProvider(BaseLLMProvider):
    """
    Groq AI LLM Provider calling Llama 3.3 70B REST API.
    """
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    # ... utilise self.GROQ_API_URL dans urllib.request.Request(...)
```
> Supprimer la fonction `_build_api_url()` et la `property API_URL`.

---

## 3. `backend/app/services/llm.py`

### ✅ État actuel (OpenAI PwC)
```python
def _build_api_url() -> str:
    """Build the chat completions URL from OPENAI_BASE_URL."""
    base = settings.OPENAI_BASE_URL.rstrip("/")
    if base.endswith("/v1"):
        return f"{base}/chat/completions"
    return f"{base}/openai/v1/chat/completions"

class GroqLLMService:
    """OpenAI-compatible LLM Service (PwC Azure OpenAI endpoint or Groq)."""

    @classmethod
    def _get_api_url(cls) -> str:
        return _build_api_url()
    # ... utilise cls._get_api_url() dans urllib.request.Request(...)
```

### ⏪ Pour revenir à Groq — remplacer par :
```python
class GroqLLMService:
    """
    Groq AI LLM Service calling Llama 3.3 70B via OpenAI-compatible REST API.
    """
    GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
    # ... utilise cls.GROQ_API_URL dans urllib.request.Request(...)
```
> Supprimer la fonction `_build_api_url()` et la méthode `_get_api_url()`.

---

## 4. `docker-compose.yml`

### ✅ État actuel (OpenAI PwC) — service `api` et `worker`
```yaml
OPENAI_API_KEY: ${OPENAI_API_KEY:?OPENAI_API_KEY must be set}
OPENAI_BASE_URL: ${OPENAI_BASE_URL:-https://api.openai.com}
OPENAI_MODEL: ${OPENAI_MODEL:-azure.gpt-4o-mini}
```

### ⏪ Pour revenir à Groq — remplacer par (dans `api` ET `worker`) :
```yaml
GROQ_API_KEY: ${GROQ_API_KEY:?GROQ_API_KEY must be set}
```

---

## 5. `.env` (fichier local, non versionné)

### ✅ État actuel (OpenAI PwC)
```env
OPENAI_API_KEY=sk-REDACTED_WAS_A_REAL_PWC_KEY
OPENAI_BASE_URL=https://genai-sharedservice-emea.pwcinternal.com
OPENAI_MODEL=azure.gpt-4o-mini
```

### ⏪ Pour revenir à Groq — remplacer par :
```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 🧠 Pourquoi les noms internes `GROQ_API_KEY` / `GROQ_MODEL` sont conservés

Pour éviter de modifier **tous les agents** (`agents/video/`, `agents/latex/`, etc.) qui importent `settings.GROQ_API_KEY` et `settings.GROQ_MODEL`, ces noms internes ont été gardés dans [`backend/app/core/config.py`](backend/app/core/config.py). Seule la variable d'environnement lue (`os.getenv(...)`) a été changée.

Résultat : **zéro modification dans les agents** — uniquement 3 fichiers de service + docker-compose.

---

## ✅ Commandes de lancement après migration

```bash
# Avec Docker Compose (recommandé)
docker compose up --build

# Manuel — Backend
set OPENAI_API_KEY=sk-REDACTED_WAS_A_REAL_PWC_KEY
set OPENAI_BASE_URL=https://genai-sharedservice-emea.pwcinternal.com
set OPENAI_MODEL=azure.gpt-4o-mini
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Manuel — Frontend
cd frontend && npm install && npm start
```
