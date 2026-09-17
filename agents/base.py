from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional

class BaseAgent(ABC):
    """
    Abstract Base Interface for CreateFlow AI agents.
    All specialized generation agents must implement these methods.
    """

    @abstractmethod
    def validate_input(self, prompt: str, options: Optional[Dict[str, Any]] = None) -> bool:
        """Validate the input prompt and options."""
        pass

    @abstractmethod
    def execute(
        self,
        job_id: str,
        prompt: str,
        progress_callback: Optional[Callable[[int, str], None]] = None
    ) -> Dict[str, Any]:
        """Execute the agent workflow and notify step updates via progress_callback."""
        pass

    @abstractmethod
    def generate_artifact(self, job_id: str, prompt: str, target_dir: str) -> str:
        """Generate the deliverable output file and return its output path."""
        pass
