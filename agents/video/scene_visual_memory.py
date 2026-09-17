"""
SceneVisualMemory -- Per-timeline memory for VideoAgent (Upgrade 2).
Tracks visual choices across scenes within a single storyboard execution to prevent
duplicate queries, repeated subjects, and duplicate assets without breaking continuity.
"""
from dataclasses import dataclass, field
from typing import Dict, Any, List, Set, Optional, Tuple
from agents.video.visual_query_schemas import VisualQueryResult
from agents.video.providers.base import MediaCandidate


@dataclass
class SceneVisualMemory:
    """
    Per-timeline visual memory instance. Created per compose_timeline() execution.
    Upgraded for Upgrade 4 Visual Continuity Engine.
    """
    used_queries: List[str] = field(default_factory=list)
    used_subjects: List[str] = field(default_factory=list)
    used_environments: List[str] = field(default_factory=list)
    used_provider_ids: List[str] = field(default_factory=list)
    used_asset_paths: Set[str] = field(default_factory=set)
    used_source_urls: Set[str] = field(default_factory=set)
    used_dominant_colors: List[List[str]] = field(default_factory=list)
    used_camera_styles: List[str] = field(default_factory=list)

    # Upgrade 4 Extensions
    used_color_histograms: List[List[float]] = field(default_factory=list)
    used_lighting_profiles: List[Any] = field(default_factory=list)
    used_framings: List[str] = field(default_factory=list)
    used_motion_trajectories: List[str] = field(default_factory=list)
    used_visual_motifs: Set[str] = field(default_factory=set)
    used_emotional_stages: List[str] = field(default_factory=list)
    provider_distribution: Dict[str, int] = field(default_factory=dict)

    def record_scene(self, vq_result: VisualQueryResult, candidate: Optional[MediaCandidate] = None, continuity_context: Optional[Any] = None):
        """Record visual choices from a completed scene composition."""
        if vq_result.primary_query:
            self.used_queries.append(vq_result.primary_query)
        if vq_result.subjects:
            self.used_subjects.extend(vq_result.subjects)
        if vq_result.environment:
            self.used_environments.append(vq_result.environment)
        if vq_result.color_palette:
            self.used_dominant_colors.append(vq_result.color_palette)
        if vq_result.camera_style:
            self.used_camera_styles.append(vq_result.camera_style)

        if candidate:
            if candidate.provider_id:
                self.used_provider_ids.append(candidate.provider_id)
                self.provider_distribution[candidate.provider_id] = self.provider_distribution.get(candidate.provider_id, 0) + 1
            if candidate.asset_path:
                self.used_asset_paths.add(candidate.asset_path)
            if candidate.remote_url:
                self.used_source_urls.add(candidate.remote_url)

        if continuity_context:
            if hasattr(continuity_context, "target_lighting"):
                self.used_lighting_profiles.append(continuity_context.target_lighting)
            if hasattr(continuity_context, "target_framing"):
                self.used_framings.append(continuity_context.target_framing.value if hasattr(continuity_context.target_framing, "value") else str(continuity_context.target_framing))
            if hasattr(continuity_context, "recommended_motion"):
                self.used_motion_trajectories.append(continuity_context.recommended_motion.value if hasattr(continuity_context.recommended_motion, "value") else str(continuity_context.recommended_motion))
            if hasattr(continuity_context, "emotional_stage"):
                self.used_emotional_stages.append(continuity_context.emotional_stage.value if hasattr(continuity_context.emotional_stage, "value") else str(continuity_context.emotional_stage))
            if hasattr(continuity_context, "motif_tags") and continuity_context.motif_tags:
                self.used_visual_motifs.update(continuity_context.motif_tags)

    def duplicate_query_penalty(self, candidate_query: str) -> float:
        """
        Calculates Jaccard similarity penalty against previously used queries.
        Returns 0.0 (no overlap) to 1.0 (exact duplicate).
        """
        if not candidate_query or not self.used_queries:
            return 0.0

        cand_clean = candidate_query.strip().lower()
        if cand_clean in [q.strip().lower() for q in self.used_queries]:
            return 1.0

        cand_words = set(cand_clean.split())
        if not cand_words:
            return 0.0

        max_overlap = 0.0
        for prev in self.used_queries:
            prev_words = set(prev.strip().lower().split())
            if not prev_words:
                continue
            intersection = cand_words & prev_words
            union = cand_words | prev_words
            jaccard = len(intersection) / max(len(union), 1)
            if jaccard > max_overlap:
                max_overlap = jaccard

        return max_overlap

    def duplicate_subject_penalty(self, subjects: List[str]) -> float:
        """
        Penalizes subjects that have appeared frequently in recent scenes.
        """
        if not subjects or not self.used_subjects:
            return 0.0

        recent_subjects = [s.strip().lower() for s in self.used_subjects[-10:]]
        if not recent_subjects:
            return 0.0

        overlap = sum(1 for s in subjects if s.strip().lower() in recent_subjects)
        return min(overlap / max(len(subjects), 1), 1.0)

    def is_duplicate_asset(self, asset_path: Optional[str], source_url: Optional[str]) -> bool:
        """
        Returns True if this exact asset path or source URL has already been used in this timeline.
        """
        if asset_path and asset_path in self.used_asset_paths:
            return True
        if source_url and source_url in self.used_source_urls:
            return True
        return False
