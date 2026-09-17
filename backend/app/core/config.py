import os
from pathlib import Path
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
STORAGE_DIR = BASE_DIR.parent / "storage" / "artifacts"
STORAGE_DIR.mkdir(parents=True, exist_ok=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "CreateFlow AI"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api"
    
    # PostgreSQL connection with SQLite fallback option
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_PORT: str = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "createflow_db")
    
    # Allows setting DATABASE_URL directly (e.g., sqlite:///./createflow.db)
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@{POSTGRES_SERVER}:{POSTGRES_PORT}/{POSTGRES_DB}"
    )
    
    # LLM API Key configuration — reads OPENAI_API_KEY from environment (PwC Azure OpenAI endpoint)
    # Internal name kept as GROQ_API_KEY to avoid cascading renames across all agents
    GROQ_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    # Default must be a model that actually exists on the configured provider: a
    # decommissioned name returns HTTP 404 and every LLM stage silently degrades
    # to its deterministic template.
    GROQ_MODEL: str = os.getenv("OPENAI_MODEL", "openai/gpt-oss-120b")

    # OpenAI-compatible base URL (PwC endpoint or standard OpenAI)
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com")

    # Pexels API Key configuration — optional, provider falls back gracefully if unset
    PEXELS_API_KEY: str = os.getenv("PEXELS_API_KEY", "")

    # NOTE: there is deliberately no TTS_ENGINE / PIPER_* setting here.
    #
    # Piper was removed at commercial remediation (GPL-3.0 engine, see LICENSES.md R6),
    # and the TTS chain reads TTS_ENGINE straight from the process environment
    # (agents/video/tts_engine.py, agents/video/kokoro_tts.py) rather than through
    # Settings. Mirroring it here served no one: nothing referenced settings.TTS_ENGINE,
    # and its stale "edge" default made .env's TTS_ENGINE=kokoro look overridden.
    # Per-video voice selection now resolves from the job's language -- see
    # agents/video/language.py.

    STORAGE_PATH: Path = STORAGE_DIR

    class Config:
        case_sensitive = True

settings = Settings()

# Startup validation: fail fast if required secrets are missing
if not settings.GROQ_API_KEY:
    raise RuntimeError(
        "OPENAI_API_KEY environment variable is not set. "
        "Set it before starting the application: "
        "  export OPENAI_API_KEY='your-key-here'  (Linux/Mac)\n"
        "  set OPENAI_API_KEY=your-key-here        (Windows)"
    )
