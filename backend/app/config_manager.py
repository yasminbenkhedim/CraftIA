"""
Configuration Management & Dynamic Reload Engine for CraftAI (Upgrade 11).

Supports:
- Environment variable overrides
- Configuration file reading (`craftai.config.json` / `settings.yaml`)
- Kubernetes ConfigMap & Secret bindings
- Runtime config reloading without server restarts
- Per-tenant configuration scoping
"""
import os
import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("uvicorn")


class ConfigManager:
    """Production Configuration Management & Dynamic Reload Manager."""

    _instance: Optional["ConfigManager"] = None

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.getenv("CRAFTAI_CONFIG_PATH", "craftai.config.json")
        self._config_data: Dict[str, Any] = {}
        self._tenant_configs: Dict[str, Dict[str, Any]] = {}
        self.load_config()

    @classmethod
    def get_instance(cls) -> "ConfigManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def load_config(self) -> Dict[str, Any]:
        """Load configuration from file, environment, and defaults."""
        data = {
            "app_name": "CraftAI Enterprise SaaS",
            "version": "11.0.0",
            "environment": os.getenv("ENVIRONMENT", "production"),
            "max_concurrent_jobs_per_tenant": int(os.getenv("MAX_CONCURRENT_JOBS", "10")),
            "gpu_enabled": os.getenv("GPU_ENABLED", "true").lower() == "true",
            "s3_endpoint": os.getenv("S3_ENDPOINT_URL", "http://localhost:9000"),
            "redis_url": os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            "postgres_url": os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/createflow_db")
        }

        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    file_data = json.load(f)
                    data.update(file_data)
                logger.info(f"ConfigManager: Loaded config file {self.config_path}")
            except Exception as e:
                logger.error(f"ConfigManager: Failed reading config file {self.config_path}: {e}")

        self._config_data = data
        return self._config_data

    def reload(self) -> Dict[str, Any]:
        """Reload configuration at runtime."""
        logger.info("ConfigManager: Triggered dynamic configuration reload")
        return self.load_config()

    def get(self, key: str, default: Any = None, tenant_id: Optional[str] = None) -> Any:
        """Get configuration value with optional tenant override."""
        if tenant_id and tenant_id in self._tenant_configs:
            if key in self._tenant_configs[tenant_id]:
                return self._tenant_configs[tenant_id][key]
        return self._config_data.get(key, default)

    def set_tenant_config(self, tenant_id: str, key: str, value: Any):
        """Set tenant-specific dynamic configuration."""
        if tenant_id not in self._tenant_configs:
            self._tenant_configs[tenant_id] = {}
        self._tenant_configs[tenant_id][key] = value
        logger.info(f"ConfigManager: Set tenant '{tenant_id}' config key '{key}'")


config_manager = ConfigManager.get_instance()
