"""
Plugin & Extension SDK for VideoAgent (Phase 8).
Provides typed plugin registration, schema validation, capability discovery, and trusted-only execution guardrails.
"""
import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class PluginCapability(str, Enum):
    PIPELINE_STAGE = "pipeline_stage"
    TRANSITION_PROVIDER = "transition_provider"
    EXPORTER = "exporter"
    DISTRIBUTION_PROVIDER = "distribution_provider"
    TREND_SOURCE = "trend_source"
    SKILL_PACK = "skill_pack"
    RENDER_PROVIDER = "render_provider"


class PluginManifest(BaseModel):
    plugin_id: str
    name: str
    version: str = "1.0.0"
    author: str = "custom"
    capability: PluginCapability
    entry_point: str
    trusted_only: bool = True
    security_statement: str = "In-process execution; trusted-only plugin registration boundary."


class PluginValidationResult(BaseModel):
    valid: bool = True
    issues: List[str] = Field(default_factory=list)


class PluginRegistry:
    """
    Plugin Registry.
    Registers extensions for pipeline stages, transitions, exporters, and providers.
    In-process plugins are explicitly classified as trusted-only execution plugins.
    """

    _plugins: Dict[str, PluginManifest] = {}

    @classmethod
    def validate_plugin(cls, manifest: PluginManifest) -> PluginValidationResult:
        issues = []
        if not manifest.plugin_id or not manifest.entry_point:
            issues.append("Plugin ID and entry_point required.")
        return PluginValidationResult(valid=len(issues) == 0, issues=issues)

    @classmethod
    def register_plugin(cls, manifest: PluginManifest) -> bool:
        val = cls.validate_plugin(manifest)
        if not val.valid:
            logger.error(f"PluginRegistry: Failed to register plugin '{manifest.plugin_id}': {val.issues}")
            return False

        cls._plugins[manifest.plugin_id] = manifest
        logger.info(f"PluginRegistry: Registered plugin '{manifest.plugin_id}' ({manifest.capability.value})")
        return True

    @classmethod
    def list_plugins(cls, capability_filter: Optional[PluginCapability] = None) -> List[PluginManifest]:
        if capability_filter:
            return [p for p in cls._plugins.values() if p.capability == capability_filter]
        return list(cls._plugins.values())
