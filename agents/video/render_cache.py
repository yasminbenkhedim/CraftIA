"""
Asset Reuse Render Cache Module for VideoAgent (Phase 6).
Avoids duplicate rendering by generating deterministic render fingerprints across prompt, storyboard, provider, profile, and render settings.
"""
import hashlib
import logging
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class RenderFingerprint(BaseModel):
    prompt_hash: str
    storyboard_hash: str
    provider_id: str
    profile_id: str
    render_settings_hash: str
    aspect_ratio: str = "16:9"

    def compute_hash(self) -> str:
        raw = f"{self.prompt_hash}:{self.storyboard_hash}:{self.provider_id}:{self.profile_id}:{self.render_settings_hash}:{self.aspect_ratio}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class CacheStatistics(BaseModel):
    total_requests: int = 0
    hits: int = 0
    misses: int = 0

    @property
    def hit_ratio(self) -> float:
        return (self.hits / self.total_requests) if self.total_requests > 0 else 0.0


class CacheResult(BaseModel):
    hit: bool
    fingerprint_hash: str
    reused_render_path: Optional[str] = None
    statistics: CacheStatistics = Field(default_factory=CacheStatistics)


class RenderCache:
    """
    Render Cache Store.
    Reuses existing rendered video files when identical fingerprints match.
    """

    _cache_store: Dict[str, str] = {}
    _stats = CacheStatistics()

    @classmethod
    def generate_fingerprint(
        cls,
        prompt: str,
        storyboard_data: str,
        provider_id: str = "default_provider",
        profile_id: str = "standard",
        render_settings: str = "standard_1080p",
        aspect_ratio: str = "16:9"
    ) -> RenderFingerprint:
        p_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:16]
        s_hash = hashlib.sha256(storyboard_data.encode("utf-8")).hexdigest()[:16]
        r_hash = hashlib.sha256(render_settings.encode("utf-8")).hexdigest()[:16]
        return RenderFingerprint(
            prompt_hash=p_hash,
            storyboard_hash=s_hash,
            provider_id=provider_id,
            profile_id=profile_id,
            render_settings_hash=r_hash,
            aspect_ratio=aspect_ratio
        )

    @classmethod
    def lookup(cls, fingerprint: RenderFingerprint) -> CacheResult:
        fp_hash = fingerprint.compute_hash()
        cls._stats.total_requests += 1

        if fp_hash in cls._cache_store:
            cls._stats.hits += 1
            render_path = cls._cache_store[fp_hash]
            logger.info(f"RenderCache: HIT for fingerprint {fp_hash[:10]}... -> '{render_path}'")
            return CacheResult(hit=True, fingerprint_hash=fp_hash, reused_render_path=render_path, statistics=cls._stats)

        cls._stats.misses += 1
        logger.info(f"RenderCache: MISS for fingerprint {fp_hash[:10]}...")
        return CacheResult(hit=False, fingerprint_hash=fp_hash, reused_render_path=None, statistics=cls._stats)

    @classmethod
    def store(cls, fingerprint: RenderFingerprint, render_path: str):
        fp_hash = fingerprint.compute_hash()
        cls._cache_store[fp_hash] = render_path
        logger.info(f"RenderCache: STORED render at '{render_path}' under fingerprint {fp_hash[:10]}...")

    @classmethod
    def invalidate(cls):
        cls._cache_store.clear()
        cls._stats = CacheStatistics()

    @classmethod
    def get_statistics(cls) -> CacheStatistics:
        return cls._stats
