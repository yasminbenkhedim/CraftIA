"""
Visual Query Schemas & Data Models for VideoAgent (Upgrade 2).
Defines dataclasses, enums, and models for visual query generation, privacy, budgets, and diagnostics.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional, Set, Tuple


class VisualQueryMode(Enum):
    DISABLED = "disabled"                    # Legacy path: scene.narration[:60]
    DETERMINISTIC_ONLY = "deterministic_only"# Fallback only, no LLM calls
    FULL = "full"                            # Batch LLM + per-scene retry + deterministic fallback


class VisualQueryPrivacyMode(Enum):
    FULL = "full"           # Full text stored in logs/cache
    TRUNCATED = "truncated" # Truncated text (40 chars) in logs/manifests; full in cache
    REDACTED = "redacted"   # Hashes only in logs/cache/manifests


@dataclass
class VisualQueryConfig:
    mode: VisualQueryMode = VisualQueryMode.FULL
    privacy_mode: VisualQueryPrivacyMode = VisualQueryPrivacyMode.TRUNCATED
    enable_llm: bool = True
    llm_temperature: float = 0.3
    llm_timeout_seconds: float = 8.0
    llm_max_retries: int = 1
    max_query_length_words: int = 8
    min_query_length_words: int = 3
    min_confidence_threshold: float = 0.4
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600            # 1 hour
    cache_max_bytes: int = 50 * 1024 * 1024  # 50 MB
    cache_max_entries_memory: int = 500
    provider_optimization_enabled: bool = True


@dataclass
class VisualQueryInput:
    scene_id: str
    scene_title: str
    narration: Optional[str]
    storyboard_title: str
    visual_overlay_type: Optional[str] = None
    background_style: str = "gradient"
    target_provider: Optional[str] = None
    previous_scene_query: Optional[str] = None
    aspect_ratio: str = "16:9"
    language: str = "en"
    domain: Optional[str] = None
    domain_keywords: List[str] = field(default_factory=list)


@dataclass
class VisualQueryResult:
    primary_query: str
    alternate_queries: List[str] = field(default_factory=list)
    negative_terms: List[str] = field(default_factory=list)
    subjects: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    environment: str = ""
    camera_style: str = "medium shot"
    mood: str = "neutral"
    lighting: str = "natural"
    color_palette: List[str] = field(default_factory=list)
    time_period: str = "contemporary"
    confidence: float = 1.0
    quality_score: float = 1.0
    specificity_score: float = 1.0
    concrete_noun_count: int = 0
    fallback_query: str = ""
    used_fallback: bool = False
    generation_source: str = "deterministic"
    llm_model: Optional[str] = None
    token_usage: Optional[int] = None
    generation_latency_ms: float = 0.0
    cache_hit: bool = False
    cache_key: Optional[str] = None
    provider_optimized_for: Optional[str] = None
    original_query_before_optimization: Optional[str] = None
    skipped_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_query": self.primary_query,
            "alternate_queries": self.alternate_queries,
            "negative_terms": self.negative_terms,
            "subjects": self.subjects,
            "actions": self.actions,
            "environment": self.environment,
            "camera_style": self.camera_style,
            "mood": self.mood,
            "lighting": self.lighting,
            "color_palette": self.color_palette,
            "time_period": self.time_period,
            "confidence": self.confidence,
            "quality_score": self.quality_score,
            "specificity_score": self.specificity_score,
            "concrete_noun_count": self.concrete_noun_count,
            "fallback_query": self.fallback_query,
            "used_fallback": self.used_fallback,
            "generation_source": self.generation_source,
            "llm_model": self.llm_model,
            "token_usage": self.token_usage,
            "generation_latency_ms": self.generation_latency_ms,
            "cache_hit": self.cache_hit,
            "cache_key": self.cache_key,
            "provider_optimized_for": self.provider_optimized_for,
            "original_query_before_optimization": self.original_query_before_optimization,
            "skipped_reason": self.skipped_reason,
        }


@dataclass
class VisualQueryDiagnostics:
    scene_id: str
    original_narration: str
    storyboard_title: str
    domain: str
    primary_query: str
    alternate_queries: List[str]
    fallback_query: str
    quality_score: float
    confidence: float
    extracted_subjects: List[str]
    extracted_actions: List[str]
    extracted_environment: str
    generation_source: str
    llm_model: Optional[str]
    token_usage: Optional[int]
    generation_latency_ms: float
    cache_hit: bool
    cache_key: Optional[str]
    provider_optimized_for: Optional[str]
    skipped_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "original_narration": self.original_narration,
            "storyboard_title": self.storyboard_title,
            "domain": self.domain,
            "primary_query": self.primary_query,
            "alternate_queries": self.alternate_queries,
            "fallback_query": self.fallback_query,
            "quality_score": self.quality_score,
            "confidence": self.confidence,
            "extracted_subjects": self.extracted_subjects,
            "extracted_actions": self.extracted_actions,
            "extracted_environment": self.extracted_environment,
            "generation_source": self.generation_source,
            "llm_model": self.llm_model,
            "token_usage": self.token_usage,
            "generation_latency_ms": self.generation_latency_ms,
            "cache_hit": self.cache_hit,
            "cache_key": self.cache_key,
            "provider_optimized_for": self.provider_optimized_for,
            "skipped_reason": self.skipped_reason,
        }


@dataclass
class VisualQueryBudget:
    max_llm_calls: int = 3
    max_tokens: int = 5000
    max_provider_searches: int = 30
    max_generation_latency_ms: float = 15000.0

    llm_calls_used: int = 0
    tokens_used: int = 0
    provider_searches_used: int = 0
    generation_latency_used_ms: float = 0.0

    exhausted_reason: Optional[str] = None

    def can_call_llm(self) -> bool:
        if self.llm_calls_used >= self.max_llm_calls:
            self.exhausted_reason = f"Max LLM calls limit reached ({self.max_llm_calls})"
            return False
        if self.tokens_used >= self.max_tokens:
            self.exhausted_reason = f"Max tokens limit reached ({self.max_tokens})"
            return False
        if self.generation_latency_used_ms >= self.max_generation_latency_ms:
            self.exhausted_reason = f"Max generation latency limit reached ({self.max_generation_latency_ms}ms)"
            return False
        return True

    def record_llm_call(self, tokens: int, latency_ms: float):
        self.llm_calls_used += 1
        self.tokens_used += tokens
        self.generation_latency_used_ms += latency_ms

    def can_search_provider(self) -> bool:
        if self.provider_searches_used >= self.max_provider_searches:
            self.exhausted_reason = f"Max provider searches limit reached ({self.max_provider_searches})"
            return False
        return True

    def record_provider_search(self):
        self.provider_searches_used += 1
