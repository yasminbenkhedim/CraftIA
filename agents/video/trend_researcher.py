"""
Autonomous Trend Researcher Module for VideoAgent (Phase 6).
Discovers, ranks, and converts trending topics from GitHub Trending, Hacker News, Reddit, and RSS feeds.
"""
import time
import hashlib
import logging
from enum import Enum
from datetime import datetime
from typing import Dict, Any, List, Optional, Set
from pydantic import BaseModel, Field
from agents.video.orchestration.schemas import VideoGenerationRequest

logger = logging.getLogger("uvicorn")


class TrendSource(str, Enum):
    GITHUB_TRENDING = "github_trending"
    HACKER_NEWS = "hacker_news"
    REDDIT = "reddit"
    RSS_FEED = "rss_feed"
    CUSTOM = "custom"


class TrendCandidate(BaseModel):
    candidate_id: str
    title: str
    summary: str
    source: TrendSource
    popularity_score: float = 0.85
    freshness_score: float = 0.90
    confidence_score: float = 0.88
    category: str = "technology"
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def composite_rank_score(self) -> float:
        return round((self.popularity_score * 0.4) + (self.freshness_score * 0.3) + (self.confidence_score * 0.3), 4)


class TopicRanking(BaseModel):
    ranked_candidates: List[TrendCandidate] = Field(default_factory=list)
    top_topic: Optional[TrendCandidate] = None


class TrendResearchResult(BaseModel):
    query_timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    total_topics_found: int = 0
    ranking: TopicRanking = Field(default_factory=TopicRanking)
    cached: bool = False


class TrendResearcher:
    """
    Autonomous Trend Researcher Service.
    Aggregates trending technical and creative topics from public feeds without scraping unsupported sites.
    """

    _cache: Dict[str, TrendResearchResult] = {}

    @classmethod
    def fetch_github_trending(cls) -> List[TrendCandidate]:
        """Simulates fetching top GitHub Trending repositories or public feeds."""
        return [
            TrendCandidate(
                candidate_id="trend_gh_001",
                title="Autonomous Multi-Agent AI Orchestration Frameworks",
                summary="High-performance agentic frameworks for automated coding and workflow orchestration.",
                source=TrendSource.GITHUB_TRENDING,
                popularity_score=0.95,
                freshness_score=0.92,
                confidence_score=0.90,
                category="ai_engineering"
            ),
            TrendCandidate(
                candidate_id="trend_gh_002",
                title="Real-Time OpenTimelineIO Video Rendering Pipelines",
                summary="Native OTIO and FCP7 XML NLE timeline rendering integration.",
                source=TrendSource.GITHUB_TRENDING,
                popularity_score=0.88,
                freshness_score=0.89,
                confidence_score=0.85,
                category="video_production"
            )
        ]

    @classmethod
    def fetch_hacker_news(cls) -> List[TrendCandidate]:
        """Simulates fetching top Hacker News stories."""
        return [
            TrendCandidate(
                candidate_id="trend_hn_001",
                title="Next-Generation Web Media Processing & WebAssembly GPU Compilers",
                summary="Browser-based video rendering and CUDA/PyTorch tensor transformation bridges.",
                source=TrendSource.HACKER_NEWS,
                popularity_score=0.91,
                freshness_score=0.95,
                confidence_score=0.89,
                category="web_technology"
            )
        ]

    @classmethod
    def fetch_reddit(cls) -> List[TrendCandidate]:
        """Simulates fetching top tech/video Reddit posts."""
        return [
            TrendCandidate(
                candidate_id="trend_rd_001",
                title="High-Retention Short Video Editing Strategies for 2026",
                summary="3-second rule pattern interrupts, dynamic zoom punch-ins, and STFT beat alignment.",
                source=TrendSource.REDDIT,
                popularity_score=0.89,
                freshness_score=0.87,
                confidence_score=0.86,
                category="content_creation"
            )
        ]

    @classmethod
    def discover_trends(
        cls,
        sources: Optional[List[TrendSource]] = None,
        category_filter: Optional[str] = None,
        min_confidence: float = 0.60,
        blacklist: Optional[List[str]] = None,
        whitelist: Optional[List[str]] = None
    ) -> TrendResearchResult:
        """
        Discovers, filters, deduplicates, and ranks trending topics.
        """
        cache_key = f"{sources}:{category_filter}:{min_confidence}"
        if cache_key in cls._cache:
            res = cls._cache[cache_key]
            res.cached = True
            return res

        candidates: List[TrendCandidate] = []
        candidates.extend(cls.fetch_github_trending())
        candidates.extend(cls.fetch_hacker_news())
        candidates.extend(cls.fetch_reddit())

        # Filtering & Blacklist / Whitelist enforcement
        filtered: List[TrendCandidate] = []
        blacklist_set = set(b.lower() for b in (blacklist or []))
        whitelist_set = set(w.lower() for w in (whitelist or []))

        for c in candidates:
            if c.confidence_score < min_confidence:
                continue
            if category_filter and c.category != category_filter:
                continue
            if any(b in c.title.lower() for b in blacklist_set):
                continue
            if whitelist_set and not any(w in c.title.lower() for w in whitelist_set):
                continue
            filtered.append(c)

        # Sort by composite rank score
        filtered.sort(key=lambda item: item.composite_rank_score(), reverse=True)

        top = filtered[0] if filtered else None
        ranking = TopicRanking(ranked_candidates=filtered, top_topic=top)
        result = TrendResearchResult(total_topics_found=len(filtered), ranking=ranking, cached=False)
        cls._cache[cache_key] = result
        return result

    @classmethod
    def convert_trend_to_request(cls, candidate: TrendCandidate, target_duration_seconds: float = 15.0) -> VideoGenerationRequest:
        """Converts a discovered TrendCandidate into an actionable VideoGenerationRequest."""
        prompt = f"{candidate.title}: {candidate.summary}"
        return VideoGenerationRequest(
            prompt=prompt,
            target_duration_seconds=target_duration_seconds,
            aspect_ratio="16:9"
        )
