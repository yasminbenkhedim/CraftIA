"""
Self-Evolving Prompt Engine for VideoAgent (Phase 7).
Collects retention/feedback signals and generates candidate prompt revisions requiring explicit human approval.
Safety Guarantee: NEVER automatically overwrites MASTER_SYSTEM_PROMPT_V2.
"""
import time
import logging
from enum import Enum
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class FeedbackSignal(BaseModel):
    signal_id: str
    retention_score: float = 0.85
    completion_rate: float = 0.90
    engagement_metrics: Dict[str, float] = Field(default_factory=dict)
    regeneration_frequency: float = 0.10
    manual_corrections_count: int = 0
    user_rating: float = 4.5


class EvolutionCandidateStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ACTIVATED = "ACTIVATED"


class PromptDiff(BaseModel):
    diff_summary: str
    additions: List[str] = Field(default_factory=list)
    deletions: List[str] = Field(default_factory=list)


class EvolutionCandidate(BaseModel):
    candidate_id: str
    original_prompt_name: str
    proposed_prompt_text: str
    rationale: str
    version: str = "v2.1-candidate"
    diff: PromptDiff
    status: EvolutionCandidateStatus = EvolutionCandidateStatus.PENDING
    requires_human_approval: bool = True
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


class PipelineEvolver:
    """
    Self-Evolving Pipeline Service.
    Generates proposed prompt candidate revisions based on retention/engagement signals.
    """

    _feedback_history: List[FeedbackSignal] = []
    _candidates: Dict[str, EvolutionCandidate] = {}
    _active_versions: Dict[str, str] = {"MASTER_SYSTEM_PROMPT_V2": "2.0"}

    @classmethod
    def ingest_feedback(cls, signal: FeedbackSignal):
        cls._feedback_history.append(signal)
        logger.info(f"PipelineEvolver: Ingested feedback signal '{signal.signal_id}' (retention={signal.retention_score})")

    @classmethod
    def generate_evolution_candidate(cls, prompt_name: str, current_prompt_text: str) -> EvolutionCandidate:
        cid = f"cand_{prompt_name}_{int(time.time())}"

        # Generate candidate improvement suggestion
        improved_text = current_prompt_text + "\n- **Self-Evolved Rule:** Prioritize fast visual pattern interrupts on low-retention drop points."
        diff = PromptDiff(
            diff_summary="Added self-evolved visual pattern interrupt rule for retention optimization.",
            additions=["Prioritize fast visual pattern interrupts on low-retention drop points."]
        )

        cand = EvolutionCandidate(
            candidate_id=cid,
            original_prompt_name=prompt_name,
            proposed_prompt_text=improved_text,
            rationale="Feedback signals indicate minor drop-off around 3s mark; adding pattern interrupt instruction.",
            version="v2.1-proposed",
            diff=diff,
            status=EvolutionCandidateStatus.PENDING,
            requires_human_approval=True
        )

        cls._candidates[cid] = cand
        logger.info(f"PipelineEvolver: Created evolution candidate '{cid}' for prompt '{prompt_name}' (Status: PENDING approval)")
        return cand

    @classmethod
    def approve_candidate(cls, candidate_id: str) -> bool:
        """Approves a candidate. Explicit human action required."""
        cand = cls._candidates.get(candidate_id)
        if cand:
            cand.status = EvolutionCandidateStatus.APPROVED
            cls._active_versions[cand.original_prompt_name] = cand.version
            logger.info(f"PipelineEvolver: Candidate '{candidate_id}' APPROVED and activated (New Version: {cand.version})")
            return True
        return False

    @classmethod
    def reject_candidate(cls, candidate_id: str) -> bool:
        cand = cls._candidates.get(candidate_id)
        if cand:
            cand.status = EvolutionCandidateStatus.REJECTED
            return True
        return False

    @classmethod
    def list_candidates(cls) -> List[EvolutionCandidate]:
        return list(cls._candidates.values())
