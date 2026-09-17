from agents.base import BaseAgent
from agents.presentation.agent import PresentationAgent
from agents.latex.agent import LaTeXReportAgent
from agents.video.agent import VideoAgent

class AgentRouter:
    """
    Routes job requests to the corresponding specialized agent implementation.
    """
    
    @staticmethod
    def get_agent(agent_type: str) -> BaseAgent:
        normalized_type = agent_type.lower().strip()
        if normalized_type in ("presentation", "pptx"):
            return PresentationAgent()
        elif normalized_type in ("latex", "report", "pdf"):
            return LaTeXReportAgent()
        elif normalized_type in ("video", "mp4"):
            return VideoAgent()
        elif normalized_type in ("multiagent", "all"):
            return PresentationAgent()
        else:
            raise ValueError(f"Unsupported agent_type: '{agent_type}'. Must be one of: presentation, latex, video, multiagent.")
