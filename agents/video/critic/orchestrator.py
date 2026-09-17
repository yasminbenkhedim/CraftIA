"""
AIVideoCritic Master Orchestrator for CraftAI (Upgrade 8).
Orchestrates evidence collection, specialist evaluators, finding graph construction, scorecards, and revision plans.
"""
import time
import logging
from typing import List, Dict, Any, Optional
from agents.video.critic.schemas import (
    CriticFinding, QualityScorecard, RevisionRecommendationPlan, CriticRunManifest
)
from agents.video.critic.evidence import CriticEvidenceCollector
from agents.video.critic.technical_critic import TechnicalOutputCritic
from agents.video.critic.finding_graph import CriticFindingGraph
from agents.video.critic.scoring import ScoreAggregator
from agents.video.critic.revision_planner import RevisionPlanner

logger = logging.getLogger("uvicorn")


class AIVideoCritic:
    """
    Master orchestrator for AI video self-evaluation and release gating.
    """

    @classmethod
    def evaluate_video(
        cls,
        storyboard: Any,
        master_scene_graph: Optional[Any] = None,
        mp4_path: Optional[str] = None
    ) -> CriticRunManifest:
        t0 = time.time()
        video_id = storyboard.title if storyboard else "video_project"

        # 1. Collect Evidence
        evidence = CriticEvidenceCollector.collect_evidence(storyboard, master_scene_graph, mp4_path)

        # 2. Run Specialist Evaluators
        findings: List[CriticFinding] = []

        from agents.video.critic.evaluators import (
            NarrativeCritic, VisualRelevanceCritic, CameraCritic,
            MotionGraphicsCritic, AudioVisualSyncCritic, AccessibilityCritic
        )

        findings.extend(NarrativeCritic.evaluate(storyboard))
        findings.extend(VisualRelevanceCritic.evaluate(storyboard))
        findings.extend(CameraCritic.evaluate(storyboard, master_scene_graph))
        findings.extend(MotionGraphicsCritic.evaluate(storyboard))
        findings.extend(AudioVisualSyncCritic.evaluate(storyboard))
        findings.extend(AccessibilityCritic.evaluate(storyboard))

        if mp4_path:
            tech_findings = TechnicalOutputCritic.evaluate_video_file(mp4_path)
            findings.extend(tech_findings)

        # 3. Construct Causal Finding Graph
        graph = CriticFindingGraph()
        for f in findings:
            graph.add_finding(f)

        root_findings = graph.get_root_cause_findings()

        # 4. Calculate Quality Scorecard & Release Verdict
        scorecard = ScoreAggregator.calculate_scorecard(video_id, root_findings)

        # 5. Synthesize Machine-Readable Revision Recommendation Plan
        rev_plan = RevisionPlanner.build_revision_plan(video_id, root_findings)

        elapsed_ms = (time.time() - t0) * 1000.0

        return CriticRunManifest(
            video_id=video_id,
            mode="production",
            findings_count=len(findings),
            scorecard=scorecard,
            revision_plan=rev_plan,
            execution_time_ms=round(elapsed_ms, 2)
        )
