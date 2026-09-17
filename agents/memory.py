import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("uvicorn")

class AgentMemoryStore:
    """
    Agent Memory System storing user preferences, theme selections,
    past artifact execution parameters, and reviewer feedback.
    """

    _MEMORY_FILE = os.path.join(os.path.dirname(__file__), "agent_memory_store.json")
    _data: Dict[str, Any] = {
        "user_preferences": {
            "theme": "corporate_navy",
            "style": "technical",
            "target_slide_count": 6
        },
        "successful_parameters": {},
        "history": []
    }

    @classmethod
    def load(cls):
        if os.path.exists(cls._MEMORY_FILE):
            try:
                with open(cls._MEMORY_FILE, "r", encoding="utf-8") as f:
                    cls._data = json.load(f)
            except Exception as e:
                logger.error(f"Error loading agent memory file: {e}")

    @classmethod
    def save(cls):
        try:
            with open(cls._MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(cls._data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving agent memory file: {e}")

    @classmethod
    def update_user_preferences(cls, prefs: Dict[str, Any]):
        cls.load()
        cls._data["user_preferences"].update(prefs)
        cls.save()

    @classmethod
    def get_user_preferences(cls) -> Dict[str, Any]:
        cls.load()
        return cls._data.get("user_preferences", {})

    @classmethod
    def record_job_execution(cls, job_id: str, agent_type: str, prompt: str, artifact_path: str, quality_score: float):
        cls.load()
        entry = {
            "job_id": job_id,
            "agent_type": agent_type,
            "prompt": prompt,
            "artifact_path": artifact_path,
            "quality_score": quality_score
        }
        cls._data["history"].append(entry)
        cls._data["successful_parameters"][agent_type] = {
            "last_prompt": prompt,
            "quality_score": quality_score,
            "artifact_path": artifact_path
        }
        cls.save()

# Initialize memory on import
AgentMemoryStore.load()
