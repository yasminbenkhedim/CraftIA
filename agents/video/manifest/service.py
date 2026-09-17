"""
Project Manifest Service for VideoAgent.
Manages atomic serialization, SHA-256 checksums, path portability, and schema migrations.
"""
import os
import json
import hashlib
import tempfile
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Callable, Tuple, List
from agents.video.manifest.schemas import EditableVideoProjectManifest

logger = logging.getLogger("uvicorn")


class ManifestMigrationRegistry:
    """Registry handling schema version migrations."""
    _migrations: Dict[Tuple[str, str], Callable[[Dict[str, Any]], Dict[str, Any]]] = {}

    @classmethod
    def register(cls, from_version: str, to_version: str, migration_func: Callable[[Dict[str, Any]], Dict[str, Any]]):
        cls._migrations[(from_version, to_version)] = migration_func

    @classmethod
    def migrate(cls, data: Dict[str, Any], target_version: str) -> Dict[str, Any]:
        curr = data.get("schema_version", "1.0.0")
        if curr == target_version:
            return data
        key = (curr, target_version)
        if key in cls._migrations:
            logger.info(f"ManifestMigrationRegistry: Migrating manifest from {curr} -> {target_version}")
            migrated = cls._migrations[key](data)
            migrated["schema_version"] = target_version
            return migrated
        logger.warning(f"ManifestMigrationRegistry: No migration path registered for {curr} -> {target_version}. Returning as-is.")
        return data


class ProjectManifestService:
    """
    Manifest Storage Service supporting atomic JSON writes, SHA-256 checksums, and path portability.
    """

    @classmethod
    def compute_manifest_checksum(cls, manifest_dict: Dict[str, Any]) -> str:
        """Computes deterministic SHA-256 checksum of normalized JSON manifest dict."""
        manifest_copy = dict(manifest_dict)
        manifest_copy.pop("manifest_checksum", None)
        serialized = json.dumps(manifest_copy, sort_keys=True, indent=2)
        return hashlib.sha256(serialized.encode('utf-8')).hexdigest()

    @classmethod
    def save_manifest(cls, manifest: EditableVideoProjectManifest, target_path: str) -> str:
        """
        Atomically saves project manifest to target_path using temporary file and atomic rename.
        """
        target_dir = os.path.dirname(os.path.abspath(target_path))
        os.makedirs(target_dir, exist_ok=True)

        manifest.updated_at = datetime.utcnow().isoformat() + "Z"
        data = manifest.model_dump(mode="json")
        data["manifest_checksum"] = cls.compute_manifest_checksum(data)
        manifest.manifest_checksum = data["manifest_checksum"]

        serialized_json = json.dumps(data, indent=2)

        # Atomic Write Pattern: write to .tmp file first, then atomic rename
        tmp_fd, tmp_path = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
        with os.fdopen(tmp_fd, 'w', encoding='utf-8') as f:
            f.write(serialized_json)

        os.replace(tmp_path, target_path)
        logger.info(f"ProjectManifestService: Atomically saved project manifest '{manifest.project_id}' -> '{target_path}' (checksum: {manifest.manifest_checksum[:10]}...)")
        return target_path

    @classmethod
    def load_manifest(cls, source_path: str) -> Tuple[EditableVideoProjectManifest, List[str]]:
        """
        Loads project manifest from JSON file, validates checksum & schema, and checks missing asset files.
        """
        warnings = []
        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Project manifest path '{source_path}' does not exist.")

        with open(source_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Migration check if needed
        data = ManifestMigrationRegistry.migrate(data, "1.0.0")

        expected_cs = data.get("manifest_checksum")
        actual_cs = cls.compute_manifest_checksum(data)
        if expected_cs and expected_cs != actual_cs:
            warnings.append(f"Manifest checksum mismatch (expected {expected_cs[:10]}, computed {actual_cs[:10]}). File may have been edited manually.")

        manifest = EditableVideoProjectManifest.model_validate(data)

        # Check missing asset files on load without raising fatal exception
        for asset in manifest.assets:
            if asset.local_path and not os.path.exists(asset.local_path):
                msg = f"Asset '{asset.asset_id}' local file missing at '{asset.local_path}'."
                asset.warnings.append(msg)
                warnings.append(msg)

        return manifest, warnings
