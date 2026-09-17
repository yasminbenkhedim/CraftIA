"""
RevisionPlanner for CraftAI (Upgrade 8).
Synthesizes machine-readable RevisionRecommendationPlans from findings without mutating project code directly.
"""
import logging
from typing import List, Dict, Any
from agents.video.critic.schemas import (
    CriticFinding, RevisionRecommendation, RevisionRecommendationPlan
)

logger = logging.getLogger("uvicorn")


class RevisionPlanner:
    """
    Synthesizes machine-readable revision recommendations outlining targeted parameters and expected improvements.
    """

    @classmethod
    def build_revision_plan(
        cls,
        video_id: str,
        findings: List[CriticFinding]
    ) -> RevisionRecommendationPlan:
        recs: List[RevisionRecommendation] = []
        dep_order: List[str] = []

        for idx, f in enumerate(findings):
            rec = RevisionRecommendation(
                related_finding_ids=[f.finding_id],
                root_cause=f.root_cause_hypothesis or f.description,
                affected_stage=f.affected_pipeline_stage,
                action_type=f.recommended_action,
                target_scene_id=f.scene_id or "scene_1",
                target_layer_id=f.layer_id,
                proposed_parameter_changes={"severity": f.severity.value, "impact": f.score_impact},
                expected_score_improvement=round(f.score_impact * 1.2, 2),
                dependency_order=idx + 1,
                automatic_fix_eligibility=f.automatic_fix_eligibility
            )
            recs.append(rec)
            dep_order.append(rec.recommendation_id)

        total_imp = round(sum(r.expected_score_improvement for r in recs), 2)

        return RevisionRecommendationPlan(
            video_id=video_id,
            recommendations=recs,
            total_expected_improvement=total_imp,
            execution_dependency_order=dep_order
        )
