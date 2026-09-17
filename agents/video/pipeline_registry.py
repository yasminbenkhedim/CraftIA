"""
Dynamic Pipeline Registry & Profile Selection Engine for VideoAgent (Phase 5).
Manages reusable pipeline profiles and automated selection evidence.
"""
import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class PipelineProfile(BaseModel):
    profile_id: str
    display_name: str
    description: str
    planning_profile: str = "deterministic"
    pacing_profile: str = "medium"
    aspect_ratio: str = "16:9"
    target_duration_range: Tuple[float, float] = (5.0, 60.0)
    subtitle_profile: str = "standard"
    transition_policy: str = "crossfade"
    audio_profile: str = "narration_music"
    render_profile: str = "standard"
    required_capabilities: Set[str] = Field(default_factory=set)
    optional_capabilities: Set[str] = Field(default_factory=set)


class PipelineSelectionEvidence(BaseModel):
    selected_profile_id: str
    detected_content_type: str
    matched_signals: List[str] = Field(default_factory=list)
    rejected_profiles: List[str] = Field(default_factory=list)
    confidence: float = 0.90
    fallback_used: bool = False


class PipelineRegistry:
    """
    Registry managing 12 pre-configured pipeline profiles and automated selection evidence.
    Single unified pipeline architecture driven by dynamic profile configurations.
    """

    _profiles: Dict[str, PipelineProfile] = {}

    @classmethod
    def initialize_defaults(cls):
        """Initializes the 12 reusable pipeline profiles."""
        profiles_data = [
            PipelineProfile(profile_id="standard", display_name="Standard General Purpose", description="Balanced general purpose video pipeline.", aspect_ratio="16:9", target_duration_range=(5.0, 60.0)),
            PipelineProfile(profile_id="tech_explainer", display_name="Tech Explainer", description="Fast-paced technical breakdown with animated text captions.", pacing_profile="fast", aspect_ratio="16:9", target_duration_range=(10.0, 45.0)),
            PipelineProfile(profile_id="social_reel", display_name="Social Reel Short", description="Vertical 9:16 high-retention reel with energetic cuts.", pacing_profile="rapid", aspect_ratio="9:16", target_duration_range=(5.0, 30.0)),
            PipelineProfile(profile_id="cinematic_trailer", display_name="Cinematic Trailer", description="Dramatic wide 16:9 trailer with slow pushes and swooshes.", pacing_profile="dramatic", aspect_ratio="16:9", target_duration_range=(15.0, 60.0)),
            PipelineProfile(profile_id="documentary_history", display_name="Documentary History", description="Informative historical narrative with archival pan-and-zoom.", pacing_profile="steady", aspect_ratio="16:9", target_duration_range=(20.0, 90.0)),
            PipelineProfile(profile_id="educational_lesson", display_name="Educational Lesson", description="Clear educational breakdown with bold subtitles.", pacing_profile="moderate", aspect_ratio="16:9", target_duration_range=(15.0, 60.0)),
            PipelineProfile(profile_id="product_demo", display_name="Product Demo", description="Sleek product showcase with clean studio lighting.", pacing_profile="clean", aspect_ratio="16:9", target_duration_range=(10.0, 30.0)),
            PipelineProfile(profile_id="news_summary", display_name="News Summary", description="Fast news bulletin with lower-third headlines.", pacing_profile="fast", aspect_ratio="16:9", target_duration_range=(15.0, 45.0)),
            PipelineProfile(profile_id="storytelling_short", display_name="Storytelling Short", description="Narrative story short optimized for engagement.", pacing_profile="engaging", aspect_ratio="9:16", target_duration_range=(5.0, 60.0)),
            PipelineProfile(profile_id="podcast_highlights", display_name="Podcast Highlights", description="Audio-first podcast highlights clip with dynamic waveform.", pacing_profile="speech_driven", aspect_ratio="9:16", target_duration_range=(15.0, 60.0)),
            PipelineProfile(profile_id="corporate_presentation", display_name="Corporate Presentation", description="Professional deck style video presentation.", pacing_profile="structured", aspect_ratio="16:9", target_duration_range=(15.0, 90.0)),
            PipelineProfile(profile_id="tutorial_screen_demo", display_name="Tutorial Screen Demo", description="Step-by-step walkthrough with callouts.", pacing_profile="clear", aspect_ratio="16:9", target_duration_range=(15.0, 90.0))
        ]
        cls._profiles = {p.profile_id: p for p in profiles_data}

    @classmethod
    def list_profiles(cls) -> List[PipelineProfile]:
        if not cls._profiles:
            cls.initialize_defaults()
        return list(cls._profiles.values())

    @classmethod
    def get_profile(cls, profile_id: str) -> Optional[PipelineProfile]:
        if not cls._profiles:
            cls.initialize_defaults()
        return cls._profiles.get(profile_id)

    @classmethod
    def select_profile(
        cls,
        prompt: str,
        target_duration: float = 15.0,
        requested_aspect_ratio: Optional[str] = None,
        manual_override: Optional[str] = None
    ) -> Tuple[PipelineProfile, PipelineSelectionEvidence]:
        """
        Selects optimal PipelineProfile and returns selection evidence explaining the decision.
        """
        if not cls._profiles:
            cls.initialize_defaults()

        # Handle Manual Override
        if manual_override and manual_override in cls._profiles:
            prof = cls._profiles[manual_override]
            evidence = PipelineSelectionEvidence(
                selected_profile_id=prof.profile_id,
                detected_content_type="manual_override",
                matched_signals=[f"Explicit user manual override to profile '{manual_override}'"],
                confidence=1.0,
                fallback_used=False
            )
            return prof, evidence

        prompt_lower = prompt.lower()
        matched_signals = []
        rejected = []

        # Content Type Detection Rules
        if "reel" in prompt_lower or "tiktok" in prompt_lower or "shorts" in prompt_lower or requested_aspect_ratio == "9:16":
            selected_id = "social_reel"
            content_type = "social_reel"
            matched_signals.append("Matched vertical video keywords (reel, tiktok, shorts, 9:16)")
        elif "tech" in prompt_lower or "code" in prompt_lower or "software" in prompt_lower or "ai" in prompt_lower:
            selected_id = "tech_explainer"
            content_type = "tech_explainer"
            matched_signals.append("Matched technology keywords (tech, code, software, ai)")
        elif "trailer" in prompt_lower or "cinematic" in prompt_lower or "movie" in prompt_lower:
            selected_id = "cinematic_trailer"
            content_type = "cinematic_trailer"
            matched_signals.append("Matched cinematic keywords (trailer, cinematic, movie)")
        elif "doc" in prompt_lower or "history" in prompt_lower:
            selected_id = "documentary_history"
            content_type = "documentary_history"
            matched_signals.append("Matched documentary keywords (doc, history)")
        else:
            selected_id = "standard"
            content_type = "general_purpose"
            matched_signals.append("Default general purpose fallback selection")

        selected_prof = cls._profiles.get(selected_id, cls._profiles["standard"])
        rejected = [pid for pid in cls._profiles if pid != selected_id][:3]

        evidence = PipelineSelectionEvidence(
            selected_profile_id=selected_prof.profile_id,
            detected_content_type=content_type,
            matched_signals=matched_signals,
            rejected_profiles=rejected,
            confidence=0.88 if selected_id != "standard" else 0.75,
            fallback_used=(selected_id == "standard")
        )
        return selected_prof, evidence
