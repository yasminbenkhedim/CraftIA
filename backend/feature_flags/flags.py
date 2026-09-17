"""
Tenant Feature Flags Engine for CraftAI (Upgrade 11).

Supports granular per-tenant feature toggles:
- Enable GPU rendering (`enable_gpu`)
- Enable AI Critic evaluation (`enable_critic`)
- Enable automatic Revisions (`enable_revision`)
- Enable Motion Graphics Engine (`enable_motion_graphics`)
- Enable Beta features (`enable_beta_features`)

Features:
- Global default fallbacks
- Per-tenant overrides
- Dynamic runtime updates without service restart
- Integration with FastAPI dependency injection & Celery workers
"""
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("uvicorn")


class FeatureFlagKeys:
    ENABLE_GPU = "enable_gpu"
    ENABLE_CRITIC = "enable_critic"
    ENABLE_REVISION = "enable_revision"
    ENABLE_MOTION_GRAPHICS = "enable_motion_graphics"
    ENABLE_BETA_FEATURES = "enable_beta_features"


DEFAULT_FLAGS: Dict[str, bool] = {
    FeatureFlagKeys.ENABLE_GPU: True,
    FeatureFlagKeys.ENABLE_CRITIC: True,
    FeatureFlagKeys.ENABLE_REVISION: True,
    FeatureFlagKeys.ENABLE_MOTION_GRAPHICS: True,
    FeatureFlagKeys.ENABLE_BETA_FEATURES: False,
}


class FeatureFlagEngine:
    """Production Multi-Tenant Feature Flag Manager."""

    _instance: Optional["FeatureFlagEngine"] = None

    def __init__(self):
        self._tenant_flags: Dict[str, Dict[str, bool]] = {}

    @classmethod
    def get_instance(cls) -> "FeatureFlagEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def is_enabled(self, feature_key: str, tenant_id: str = "global") -> bool:
        """Check if feature is enabled for given tenant."""
        tenant_overrides = self._tenant_flags.get(tenant_id, {})
        if feature_key in tenant_overrides:
            return tenant_overrides[feature_key]
        return DEFAULT_FLAGS.get(feature_key, False)

    def set_tenant_feature(self, tenant_id: str, feature_key: str, enabled: bool):
        """Set feature flag override for a tenant."""
        if tenant_id not in self._tenant_flags:
            self._tenant_flags[tenant_id] = {}
        self._tenant_flags[tenant_id][feature_key] = enabled
        logger.info(f"FeatureFlagEngine: Tenant '{tenant_id}' set {feature_key} -> {enabled}")

    def get_tenant_flags(self, tenant_id: str) -> Dict[str, bool]:
        """Get all feature flags for a tenant (merged with defaults)."""
        merged = dict(DEFAULT_FLAGS)
        merged.update(self._tenant_flags.get(tenant_id, {}))
        return merged


feature_flags = FeatureFlagEngine.get_instance()
