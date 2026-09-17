"""
QualityScorecard Aggregator & Release Gate Policy for CraftAI (Upgrade 8).
Calculates 14 quality dimensions, applies severity penalties, and evaluates release verdicts.
"""
import logging
from typing import List, Dict, Any, Tuple
from agents.video.critic.schemas import (
    CriticFinding, FindingSeverity, QualityScorecard, ReleaseVerdict
)

logger = logging.getLogger("uvicorn")


class ScoreAggregator:
    """
    Calculates QualityScorecard dimensions and evaluates VideoReleaseGate.
    """

    @classmethod
    def calculate_scorecard(
        cls,
        video_id: str,
        findings: List[CriticFinding]
    ) -> QualityScorecard:
        scorecard = QualityScorecard(video_id=video_id)

        blockers = [f for f in findings if f.severity == FindingSeverity.BLOCKER]
        criticals = [f for f in findings if f.severity == FindingSeverity.CRITICAL]
        highs = [f for f in findings if f.severity == FindingSeverity.HIGH]
        mediums = [f for f in findings if f.severity in (FindingSeverity.MEDIUM, FindingSeverity.LOW, FindingSeverity.INFO)]

        scorecard.blocker_count = len(blockers)
        scorecard.warning_count = len(criticals) + len(highs) + len(mediums)

        # Apply specific dimension penalties based on finding types
        for f in findings:
            if f.critic_type == "narrative":
                scorecard.narrative_quality = max(0.0, round(scorecard.narrative_quality - f.score_impact, 2))
            elif f.critic_type == "visual":
                scorecard.semantic_relevance = max(0.0, round(scorecard.semantic_relevance - f.score_impact, 2))
            elif f.critic_type == "camera":
                scorecard.camera_quality = max(0.0, round(scorecard.camera_quality - f.score_impact, 2))
            elif f.critic_type == "motion_graphics":
                scorecard.motion_graphics_quality = max(0.0, round(scorecard.motion_graphics_quality - f.score_impact, 2))
            elif f.critic_type == "audio_sync":
                scorecard.synchronization_quality = max(0.0, round(scorecard.synchronization_quality - f.score_impact, 2))
            elif f.critic_type == "accessibility":
                scorecard.accessibility_score = max(0.0, round(scorecard.accessibility_score - f.score_impact, 2))
            elif f.critic_type == "technical":
                scorecard.technical_integrity = max(0.0, round(scorecard.technical_integrity - f.score_impact, 2))

        penalty = sum(f.score_impact for f in findings)
        scorecard.overall_production_quality = max(0.0, round(1.0 - penalty, 2))

        # Evaluate Calibrated Release Gate Verdict
        if scorecard.blocker_count > 0:
            scorecard.release_verdict = ReleaseVerdict.BLOCKED
        elif len(criticals) > 0:
            scorecard.release_verdict = ReleaseVerdict.REVISION_REQUIRED
        elif len(highs) > 0:
            scorecard.release_verdict = ReleaseVerdict.REVISION_REQUIRED
        elif len(mediums) > 0:
            scorecard.release_verdict = ReleaseVerdict.READY_WITH_WARNINGS
        else:
            scorecard.release_verdict = ReleaseVerdict.READY

        return scorecard
