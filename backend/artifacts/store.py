"""
Enhanced ContentAddressedArtifactStore for CraftAI (Upgrade 10 Corrective).
Immutable SHA-256 content-addressed storage with tenant isolation, alias management,
deduplication, checksum validation, and overwrite prevention.
"""
import hashlib
import time
import logging
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class ArtifactRecord(BaseModel):
    """Immutable artifact metadata stored alongside content."""
    artifact_key: str              # artifacts/{sha256_prefix}/{sha256}
    content_hash: str              # full SHA-256 hex
    tenant_id: str
    size_bytes: int
    content_type: str = "application/octet-stream"
    producer_stage: str = ""
    producer_version: str = "v1.0"
    created_at: float = Field(default_factory=time.time)
    retention_class: str = "standard"


class ArtifactAlias(BaseModel):
    """Mutable logical reference pointing to an immutable artifact."""
    alias_path: str                # jobs/{job_id}/latest/final_video
    artifact_key: str              # points to immutable object
    tenant_id: str
    updated_at: float = Field(default_factory=time.time)


class ContentAddressedArtifactStore:
    """
    Immutable content-addressed storage. Objects keyed by SHA-256.
    Identical content reuses the same object. Overwrites are rejected.
    Cross-tenant access is denied. Mutable aliases reference immutable objects.
    """

    def __init__(self):
        self.objects: Dict[str, bytes] = {}           # key -> content
        self.records: Dict[str, ArtifactRecord] = {}  # key -> metadata
        self.aliases: Dict[str, ArtifactAlias] = {}   # alias_path -> alias

    def _content_key(self, content_hash: str) -> str:
        return f"artifacts/{content_hash[:2]}/{content_hash}"

    def put_artifact(self, content: bytes, tenant_id: str,
                     content_type: str = "application/octet-stream",
                     producer_stage: str = "") -> ArtifactRecord:
        content_hash = hashlib.sha256(content).hexdigest()
        key = self._content_key(content_hash)

        if key in self.objects:
            # Content deduplication: identical content reuses the same object
            existing = self.records[key]
            logger.info(f"Content deduplication: reusing existing artifact {key}")
            return existing

        self.objects[key] = content
        record = ArtifactRecord(
            artifact_key=key,
            content_hash=content_hash,
            tenant_id=tenant_id,
            size_bytes=len(content),
            content_type=content_type,
            producer_stage=producer_stage,
        )
        self.records[key] = record
        return record

    def get_artifact(self, artifact_key: str, tenant_id: str) -> Optional[bytes]:
        if artifact_key not in self.records:
            return None
        record = self.records[artifact_key]
        if record.tenant_id != tenant_id:
            logger.warning(f"DENIED: tenant '{tenant_id}' attempted access to artifact owned by '{record.tenant_id}'")
            return None
        return self.objects.get(artifact_key)

    def overwrite_artifact(self, artifact_key: str, new_content: bytes) -> Tuple[bool, str]:
        """Immutable objects cannot be overwritten. Always returns failure."""
        if artifact_key in self.objects:
            return False, f"REJECTED: immutable artifact '{artifact_key}' cannot be overwritten"
        return False, f"Artifact '{artifact_key}' does not exist"

    def validate_checksum(self, artifact_key: str) -> Tuple[bool, str]:
        """Validates stored content matches its SHA-256 key."""
        if artifact_key not in self.objects:
            return False, "Artifact not found"
        content = self.objects[artifact_key]
        actual_hash = hashlib.sha256(content).hexdigest()
        expected_hash = self.records[artifact_key].content_hash
        if actual_hash != expected_hash:
            return False, f"CHECKSUM MISMATCH: expected {expected_hash}, got {actual_hash}"
        return True, "Checksum valid"

    def set_alias(self, alias_path: str, artifact_key: str, tenant_id: str) -> ArtifactAlias:
        """Creates or updates a mutable alias pointing to an immutable artifact."""
        alias = ArtifactAlias(alias_path=alias_path, artifact_key=artifact_key, tenant_id=tenant_id)
        self.aliases[alias_path] = alias
        return alias

    def resolve_alias(self, alias_path: str, tenant_id: str) -> Optional[str]:
        """Resolves a mutable alias to its immutable artifact key."""
        if alias_path not in self.aliases:
            return None
        alias = self.aliases[alias_path]
        if alias.tenant_id != tenant_id:
            return None
        return alias.artifact_key

    def count_objects(self) -> int:
        return len(self.objects)
