"""
Centralised .env bootstrap for CraftAI.

Importing this module (or calling load_project_env()) loads the project's root
`.env` file into os.environ BEFORE any application module that reads
os.environ / instantiates Settings is imported.

Why this exists:
  backend/app/core/config.py validates required secrets AT IMPORT TIME
  (raises RuntimeError if OPENAI_API_KEY is missing). It only reads
  os.environ, never the .env file. Likewise agents/video/wav2lip_engine.py
  reads WAV2LIP_* from os.environ at import time. Without this bootstrap the
  .env values (PEXELS_API_KEY, WAV2LIP_*, ...) are never seen by the app.

Precedence:
  Real, pre-existing environment variables WIN over the .env file
  (override=False). This keeps the .ps1 launch scripts and container/K8s env
  authoritative while letting the .env provide everything else.
"""
import os
from pathlib import Path

# Project root = two levels up from this file (backend/ -> project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_PATH = _PROJECT_ROOT / ".env"

_loaded = False


def load_project_env() -> bool:
    """Loads the root .env into os.environ once. Returns True if a file was loaded."""
    global _loaded
    if _loaded:
        return True
    try:
        from dotenv import load_dotenv
    except Exception:
        # python-dotenv not installed; fall back to a tiny manual parser so the
        # app still picks up the .env values instead of silently ignoring them.
        return _manual_load()

    if _ENV_PATH.exists():
        # override=False: never clobber variables already set by the shell /
        # launch scripts / container environment.
        load_dotenv(dotenv_path=str(_ENV_PATH), override=False)
        _loaded = True
        return True
    return False


def _manual_load() -> bool:
    global _loaded
    if not _ENV_PATH.exists():
        return False
    with open(_ENV_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())
    _loaded = True
    return True


# Load immediately on import so `import backend.env_bootstrap` is enough.
load_project_env()
