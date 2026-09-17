"""
MCP Prompt Templates Catalog for VideoAgent (Phase 5).
"""
from typing import Dict, Any, List
from backend.app.mcp.schemas import MCPPromptItem


class MCPPromptCatalog:
    """Prompt Templates Catalog for MCP Clients."""

    @classmethod
    def list_prompts(cls) -> List[MCPPromptItem]:
        return [
            MCPPromptItem(name="explain_project", description="Explains project structure and lifecycle manifest status.", arguments=[{"name": "project_id", "required": True}]),
            MCPPromptItem(name="summarize_timeline", description="Summarizes timeline clips and audio track structure.", arguments=[{"name": "project_id", "required": True}]),
            MCPPromptItem(name="suggest_pipeline_profile", description="Suggests optimal pipeline profile for a prompt.", arguments=[{"name": "prompt", "required": True}]),
            MCPPromptItem(name="suggest_conversational_edit", description="Generates natural language editing command suggestion.", arguments=[{"name": "goal", "required": True}]),
            MCPPromptItem(name="debugging_assistant", description="Assists in diagnosing pipeline or render failure logs.", arguments=[{"name": "error_log", "required": True}])
        ]

    @classmethod
    def get_prompt(cls, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        if name == "explain_project":
            pid = arguments.get("project_id", "unknown")
            return {"prompt": f"Please analyze project {pid} and summarize its screenplay, director brief, and lifecycle state."}
        if name == "suggest_pipeline_profile":
            p = arguments.get("prompt", "")
            return {"prompt": f"Analyze prompt '{p}' and recommend the best VideoAgent pipeline profile (e.g. tech_explainer, social_reel)."}
        return {"name": name, "prompt": f"Assist with task: {name}."}
