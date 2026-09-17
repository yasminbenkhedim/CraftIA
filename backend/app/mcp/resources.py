"""
MCP Read-Only Resource Handlers for VideoAgent (Phase 5).
Exposes manifests, skill packs, pipeline profiles, continuity metadata, and renderer capabilities as read-only resources.
"""
import json
import os
from typing import Dict, Any, List, Optional
from backend.app.mcp.schemas import MCPResourceItem


class MCPResourceCatalog:
    """Read-only Resource Manager for MCP Clients."""

    @classmethod
    def list_resources(cls) -> List[MCPResourceItem]:
        return [
            MCPResourceItem(uri="videoagent://manifests/latest", name="Latest Manifest", description="Read-only access to the latest project manifest."),
            MCPResourceItem(uri="videoagent://skills/list", name="Skill Packs Catalog", description="List of registered editing skill packs."),
            MCPResourceItem(uri="videoagent://pipeline/profiles", name="Pipeline Profiles Catalog", description="Dynamic pipeline profiles registry."),
            MCPResourceItem(uri="videoagent://continuity/metadata", name="Continuity Metadata", description="Visual style anchor continuity records."),
            MCPResourceItem(uri="videoagent://renderer/capabilities", name="Renderer Capabilities", description="System probe for FFmpeg and GPU compositor capabilities.")
        ]

    @classmethod
    def read_resource(cls, uri: str) -> Dict[str, Any]:
        if uri == "videoagent://pipeline/profiles":
            from agents.video.pipeline_registry import PipelineRegistry
            return {"profiles": [p.model_dump() for p in PipelineRegistry.list_profiles()]}

        if uri == "videoagent://skills/list":
            from agents.video.skills.skill_archiver import SkillArchiver
            return {"skill_packs": ["cinematic_doc", "social_reel_fast"]}

        if uri == "videoagent://renderer/capabilities":
            from agents.video.python_editor.gpu_compositor import GPUCompositor
            return GPUCompositor.get_device_report()

        if uri == "videoagent://continuity/metadata":
            return {"status": "ok", "continuity_mode": "Retrieval-assisted continuity recommendation"}

        return {"uri": uri, "content": "read_only_data"}
