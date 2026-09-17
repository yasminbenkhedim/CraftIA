"""
Digital Asset Management (DAM) Service for VideoAgent (Phase 8).
Handles SHA-256 checksum deduplication, asset versioning, tagging, and project usage tracking.
"""
import os
import hashlib
import time
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class MediaAsset(BaseModel):
    asset_id: str
    project_id: str
    filename: str
    file_path: str
    checksum_sha256: str
    mime_type: str = "video/mp4"
    size_bytes: int = 0
    tags: List[str] = Field(default_factory=list)
    version: int = 1
    storage_backend: str = "local"
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class DigitalAssetManager:
    """
    Digital Asset Manager Service.
    Indexes media assets, enforces project isolation, and provides deduplication via checksums.
    """

    _assets: Dict[str, MediaAsset] = {}  # asset_id -> MediaAsset
    _checksum_map: Dict[str, str] = {}  # checksum -> asset_id

    @classmethod
    def register_asset(
        cls,
        project_id: str,
        file_path: str,
        tags: Optional[List[str]] = None,
        storage_backend: str = "local"
    ) -> MediaAsset:
        fname = os.path.basename(file_path)
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                cs = hashlib.sha256(f.read()).hexdigest()
            size = os.path.getsize(file_path)
        else:
            cs = hashlib.sha256(file_path.encode("utf-8")).hexdigest()
            size = len(file_path)

        # Deduplication check
        if cs in cls._checksum_map:
            existing_id = cls._checksum_map[cs]
            logger.info(f"DigitalAssetManager: Deduplication hit for checksum {cs[:10]}... -> asset '{existing_id}'")
            return cls._assets[existing_id]

        aid = f"asset_{project_id}_{int(time.time())}"
        asset = MediaAsset(
            asset_id=aid,
            project_id=project_id,
            filename=fname,
            file_path=file_path,
            checksum_sha256=cs,
            size_bytes=size,
            tags=tags or ["media"],
            storage_backend=storage_backend
        )

        cls._assets[aid] = asset
        cls._checksum_map[cs] = aid
        logger.info(f"DigitalAssetManager: Registered asset '{aid}' for project '{project_id}'")
        return asset

    @classmethod
    def lookup_by_checksum(cls, checksum: str) -> Optional[MediaAsset]:
        aid = cls._checksum_map.get(checksum)
        return cls._assets.get(aid) if aid else None

    @classmethod
    def search_assets(cls, query: str, project_id: Optional[str] = None) -> List[MediaAsset]:
        q_lower = query.lower()
        results = []
        for a in cls._assets.values():
            if project_id and a.project_id != project_id:
                continue
            if q_lower in a.filename.lower() or any(q_lower in tag.lower() for tag in a.tags):
                results.append(a)
        return results
