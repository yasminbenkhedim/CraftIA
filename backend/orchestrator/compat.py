"""
Import resolver for CraftAI backend modules.

Handles both import styles:
- `from backend.app.core.database import ...` (when PYTHONPATH=project_root)
- `from app.core.database import ...` (when PYTHONPATH=backend/)
"""


def get_db_session():
    """Get a database session using the existing CraftAI SessionLocal."""
    try:
        from backend.app.core.database import SessionLocal
        return SessionLocal()
    except ImportError:
        from app.core.database import SessionLocal
        return SessionLocal()


def get_models():
    """Import all orchestrator models."""
    try:
        from orchestrator import models
        return models
    except ImportError:
        from backend.orchestrator import models
        return models
