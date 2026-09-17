"""
Provider Query Adapters -- Provider-Specific Search Optimizers for VideoAgent (Upgrade 2).
Adapts neutral VisualQueryResult objects into provider-optimized primary and alternate queries.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from agents.video.visual_query_schemas import VisualQueryResult, VisualQueryInput


class ProviderQueryAdapter(ABC):
    """
    Abstract interface for provider-specific query adapters.
    """

    @abstractmethod
    def adapt(self, vq_result: VisualQueryResult, vq_input: Optional[VisualQueryInput] = None) -> VisualQueryResult:
        """
        Derives provider-optimized queries from a neutral VisualQueryResult.
        Returns a new or updated VisualQueryResult object.
        """
        pass


class OpenverseQueryAdapter(ProviderQueryAdapter):
    """
    Adapter for Openverse API.
    - Favors short, concrete noun phrases (2-4 words)
    - Strips prepositions, articles, and abstract modifiers
    - Limits primary query to <= 60 characters
    - Produces up to 3 bounded alternate queries
    """

    def adapt(self, vq_result: VisualQueryResult, vq_input: Optional[VisualQueryInput] = None) -> VisualQueryResult:
        res = VisualQueryResult(**vq_result.to_dict())
        res.original_query_before_optimization = vq_result.primary_query
        res.provider_optimized_for = "openverse_stock"

        # Build short concrete query: 2-3 subjects + 1 environment word
        subjects = [s.lower().strip() for s in res.subjects if s.strip()]
        env_words = [w.lower().strip() for w in res.environment.split() if w.strip()] if res.environment else []

        parts = []
        if subjects:
            parts.extend(subjects[:2])
        if env_words:
            parts.append(env_words[0])

        if not parts:
            parts = [w.lower().strip() for w in res.primary_query.split() if w.strip()][:3]

        primary = " ".join(parts[:4])[:60]
        res.primary_query = primary if primary else "abstract background"

        # Bounded alternate queries
        alternates = []
        if subjects:
            alt1 = " ".join(subjects[:1] + (env_words[:1] if env_words else []))
            if alt1 and alt1 != primary:
                alternates.append(alt1[:60])

        if len(subjects) >= 2:
            alt2 = " ".join(subjects[:2])
            if alt2 and alt2 != primary and alt2 not in alternates:
                alternates.append(alt2[:60])

        if res.alternate_queries:
            for alt in res.alternate_queries:
                alt_clean = " ".join(alt.lower().split()[:3])[:60]
                if alt_clean and alt_clean != primary and alt_clean not in alternates:
                    alternates.append(alt_clean)
                if len(alternates) >= 2:
                    break

        res.alternate_queries = alternates[:2]
        return res


class PexelsQueryAdapter(ProviderQueryAdapter):
    """
    Adapter for Pexels API.
    - Allows natural visual phrases (3-6 words)
    - Incorporates visible action, subject, and environment
    - Limits primary query to <= 80 characters
    - Produces up to 3 bounded alternate queries
    """

    def adapt(self, vq_result: VisualQueryResult, vq_input: Optional[VisualQueryInput] = None) -> VisualQueryResult:
        res = VisualQueryResult(**vq_result.to_dict())
        res.original_query_before_optimization = vq_result.primary_query
        res.provider_optimized_for = "pexels_stock"

        subjects = [s.lower().strip() for s in res.subjects if s.strip()]
        actions = [a.lower().strip() for a in res.actions if a.strip()]
        env = res.environment.lower().strip() if res.environment else ""

        parts = []
        if subjects:
            parts.append(subjects[0])
        if actions:
            parts.append(actions[0])
        if len(subjects) >= 2:
            parts.append(subjects[1])
        if env:
            parts.append(env)

        if not parts:
            parts = [w.lower().strip() for w in res.primary_query.split() if w.strip()][:5]

        primary = " ".join(parts[:6])[:80]
        res.primary_query = primary if primary else "nature landscape background"

        alternates = []
        if subjects and env:
            alt1 = f"{subjects[0]} {env}"
            if alt1 != primary:
                alternates.append(alt1[:80])

        if res.alternate_queries:
            for alt in res.alternate_queries:
                alt_clean = " ".join(alt.lower().split()[:5])[:80]
                if alt_clean and alt_clean != primary and alt_clean not in alternates:
                    alternates.append(alt_clean)
                if len(alternates) >= 2:
                    break

        res.alternate_queries = alternates[:2]
        return res


class PexelsVideoQueryAdapter(PexelsQueryAdapter):
    """
    Adapter for Pexels Videos API. Reuses the Pexels photo query heuristics
    (natural visual phrases favor stock footage search just as well as stills).
    """

    def adapt(self, vq_result: VisualQueryResult, vq_input: Optional[VisualQueryInput] = None) -> VisualQueryResult:
        res = super().adapt(vq_result, vq_input)
        res.provider_optimized_for = "pexels_video"
        return res


class LocalAssetQueryAdapter(ProviderQueryAdapter):
    """
    Adapter for Local Asset Provider.
    """

    def adapt(self, vq_result: VisualQueryResult, vq_input: Optional[VisualQueryInput] = None) -> VisualQueryResult:
        res = VisualQueryResult(**vq_result.to_dict())
        res.provider_optimized_for = "local_asset"
        res.original_query_before_optimization = vq_result.primary_query
        return res


class GenblazeImageQueryAdapter(ProviderQueryAdapter):
    """
    Adapter for Genblaze Image Provider (Generative AI Image Prompting).
    """

    def adapt(self, vq_result: VisualQueryResult, vq_input: Optional[VisualQueryInput] = None) -> VisualQueryResult:
        res = VisualQueryResult(**vq_result.to_dict())
        res.provider_optimized_for = "genblaze_image"
        res.original_query_before_optimization = vq_result.primary_query
        # Construct detailed image prompt from visual attributes
        prompt_parts = []
        if res.subjects:
            prompt_parts.append(f"a photo of {', '.join(res.subjects)}")
        if res.actions:
            prompt_parts.append(f"showing {res.actions[0]}")
        if res.environment:
            prompt_parts.append(f"in a {res.environment}")
        if res.camera_style:
            prompt_parts.append(f"{res.camera_style}")
        if res.lighting:
            prompt_parts.append(f"{res.lighting} lighting")

        res.primary_query = ", ".join(prompt_parts) if prompt_parts else res.primary_query
        return res


class QueryAdapterRegistry:
    """
    Registry for resolving provider query adapters.
    """
    _adapters: Dict[str, ProviderQueryAdapter] = {
        "openverse_stock": OpenverseQueryAdapter(),
        "pexels_stock": PexelsQueryAdapter(),
        "pexels_video": PexelsVideoQueryAdapter(),
        "local_asset": LocalAssetQueryAdapter(),
        "genblaze_image": GenblazeImageQueryAdapter(),
    }

    @classmethod
    def adapt(cls, provider_id: str, vq_result: VisualQueryResult, vq_input: Optional[VisualQueryInput] = None) -> VisualQueryResult:
        adapter = cls._adapters.get(provider_id)
        if adapter:
            return adapter.adapt(vq_result, vq_input)
        return vq_result
