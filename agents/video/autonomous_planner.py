"""
Autonomous Planning Agent Module for VideoAgent (Phase 6).
Orchestrates autonomous topic discovery, pipeline profile selection, and video request generation with full audit evidence.
"""
import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from agents.video.trend_researcher import TrendResearcher, TrendCandidate, TrendResearchResult
from agents.video.pipeline_registry import PipelineRegistry, PipelineProfile, PipelineSelectionEvidence
from agents.video.orchestration.schemas import VideoGenerationRequest

logger = logging.getLogger("uvicorn")


class PlanningStrategy(str, Enum):
    AUTONOMOUS_TREND_DRIVEN = "autonomous_trend_driven"
    MANUAL_OVERRIDE = "manual_override"
    SCHEDULED_BATCH = "scheduled_batch"


class PlanningDecision(BaseModel):
    selected_topic: str
    rejected_topics: List[str] = Field(default_factory=list)
    selected_pipeline_profile: str
    expected_duration: float = 15.0
    target_audience: str = "general_technology"
    confidence_score: float = 0.90


class PlanningEvidence(BaseModel):
    decision_rationale: str
    matched_trend_source: str
    content_signals: List[str] = Field(default_factory=list)
    manual_override_applied: bool = False


class PlanningResult(BaseModel):
    strategy: PlanningStrategy
    decision: PlanningDecision
    evidence: PlanningEvidence
    video_request: VideoGenerationRequest


class AutonomousPlanner:
    """
    Autonomous Planner Service.
    Converts trend research into pipeline requests and explains why decisions were made.
    """

    @classmethod
    def plan_autonomous_video(
        cls,
        manual_prompt: Optional[str] = None,
        category_filter: Optional[str] = None,
        manual_profile: Optional[str] = None,
        target_duration: float = 15.0
    ) -> PlanningResult:
        """
        Orchestrates autonomous topic selection and pipeline profiling.
        Manual prompt or profile selection explicitly overrides autonomous decisions.
        """
        if manual_prompt:
            profile, ev = PipelineRegistry.select_profile(manual_prompt, target_duration=target_duration, manual_override=manual_profile)
            req = VideoGenerationRequest(prompt=manual_prompt, target_duration_seconds=target_duration)
            decision = PlanningDecision(
                selected_topic=manual_prompt,
                selected_pipeline_profile=profile.profile_id,
                expected_duration=target_duration,
                confidence_score=1.0
            )
            evidence = PlanningEvidence(
                decision_rationale=f"Manual user override applied for prompt '{manual_prompt}'",
                matched_trend_source="user_explicit",
                content_signals=["user_provided_prompt"],
                manual_override_applied=True
            )
            return PlanningResult(strategy=PlanningStrategy.MANUAL_OVERRIDE, decision=decision, evidence=evidence, video_request=req)

        # Autonomous Trend Research
        trends: TrendResearchResult = TrendResearcher.discover_trends(category_filter=category_filter)
        if not trends.ranking.top_topic:
            # Fallback default topic
            top_candidate = TrendCandidate(
                candidate_id="trend_fallback",
                title="CreateFlow-AI VideoAgent Architecture Overview",
                summary="Autonomous multi-stage AI video generation engine.",
                source="custom"
            )
        else:
            top_candidate = trends.ranking.top_topic

        profile, sel_evidence = PipelineRegistry.select_profile(
            f"{top_candidate.title}: {top_candidate.summary}",
            target_duration=target_duration,
            manual_override=manual_profile
        )
        req = TrendResearcher.convert_trend_to_request(top_candidate, target_duration_seconds=target_duration)

        rejected = [c.title for c in trends.ranking.ranked_candidates[1:4]]
        decision = PlanningDecision(
            selected_topic=top_candidate.title,
            rejected_topics=rejected,
            selected_pipeline_profile=profile.profile_id,
            expected_duration=target_duration,
            confidence_score=top_candidate.confidence_score
        )
        evidence = PlanningEvidence(
            decision_rationale=f"Selected top trending topic from '{top_candidate.source.value}' with popularity score {top_candidate.popularity_score}",
            matched_trend_source=top_candidate.source.value,
            content_signals=sel_evidence.matched_signals,
            manual_override_applied=False
        )
        return PlanningResult(strategy=PlanningStrategy.AUTONOMOUS_TREND_DRIVEN, decision=decision, evidence=evidence, video_request=req)
