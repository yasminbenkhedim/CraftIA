import time
import logging
from typing import Dict, Any, List, Callable

logger = logging.getLogger("uvicorn")

class AgentEventStream:
    """
    Event-driven stream manager inspired by Orxhestra.
    Manages agent event subscriptions and real-time execution event broadcasting.
    """

    def __init__(self, job_id: str):
        self.job_id = job_id
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._event_history: List[Dict[str, Any]] = []

    def subscribe(self, listener: Callable[[Dict[str, Any]], None]):
        self._listeners.append(listener)

    def publish_event(self, event_type: str, step_name: str, progress: int, payload: Dict[str, Any] = None):
        event = {
            "job_id": self.job_id,
            "event_type": event_type,
            "step_name": step_name,
            "progress": progress,
            "timestamp": time.time(),
            "payload": payload or {}
        }
        self._event_history.append(event)
        logger.info(f"AgentEventStream [{self.job_id}] [{event_type}] {step_name} ({progress}%)")

        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                logger.error(f"Error notifying event stream listener: {e}")

    def get_history(self) -> List[Dict[str, Any]]:
        return self._event_history
