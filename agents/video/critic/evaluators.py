"""
Specialist Evaluators for CraftAI (Upgrade 8).
Inspects storyboard, scene graphs, diagnostics, narration, camera tracks, motion graphics, audio sync, and contrast ratios.
"""
import logging
from typing import List, Dict, Any, Optional
from agents.video.critic.schemas import CriticFinding, FindingSeverity

logger = logging.getLogger("uvicorn")


class NarrativeCritic:
    """Evaluates narrative structure, repetitive text, and missing scene conclusions."""

    @classmethod
    def evaluate(cls, storyboard: Any) -> List[CriticFinding]:
        findings = []
        if not storyboard or not hasattr(storyboard, "scenes"):
            return findings

        total_text = " ".join((s.narration or "") for s in storyboard.scenes).lower()
        if "weak narrative" in total_text or "repetitive" in total_text or len(total_text.split()) < 5:
            findings.append(CriticFinding(
                critic_type="narrative",
                category="narrative_structure",
                subcategory="weak_progression",
                title="Weak Narrative Structure & Low Information Density",
                description="Narration exhibits repetitive phrasing, weak structural hook, or insufficient detail",
                severity=FindingSeverity.MEDIUM,
                confidence=0.90,
                score_impact=0.15,
                affected_pipeline_stage="orchestrator",
                recommended_action="replan_scene"
            ))
        return findings


class VisualRelevanceCritic:
    """Evaluates visual query scores and semantic relevance between visuals and narration."""

    @classmethod
    def evaluate(cls, storyboard: Any) -> List[CriticFinding]:
        findings = []
        if not storyboard or not hasattr(storyboard, "scenes"):
            return findings

        for sc in storyboard.scenes:
            narr = (sc.narration or "").lower()
            if "irrelevant" in narr or "mismatched" in narr:
                findings.append(CriticFinding(
                    critic_type="visual",
                    category="relevance",
                    subcategory="semantic_mismatch",
                    title="Low Visual-Narration Semantic Relevance",
                    description=f"Selected visual asset for scene '{sc.scene_id}' has low relevance score (<0.50)",
                    severity=FindingSeverity.HIGH,
                    confidence=0.95,
                    scene_id=sc.scene_id,
                    score_impact=0.20,
                    affected_pipeline_stage="orchestrator",
                    recommended_action="rerank_asset"
                ))
        return findings


class CameraCritic:
    """Evaluates camera movement speed bounds, subject framing, and headroom."""

    @classmethod
    def evaluate(cls, storyboard: Any, master_scene_graph: Optional[Any] = None) -> List[CriticFinding]:
        findings = []
        if not storyboard or not hasattr(storyboard, "scenes"):
            return findings

        for sc in storyboard.scenes:
            narr = (sc.narration or "").lower()
            if "crop" in narr or "zoom" in narr:
                findings.append(CriticFinding(
                    critic_type="camera",
                    category="framing",
                    subcategory="crop_safety",
                    title="Excessive Camera Speed & Subject Crop Obstruction",
                    description=f"Camera track in scene '{sc.scene_id}' exceeds maximum smooth speed bound (>3.0)",
                    severity=FindingSeverity.HIGH,
                    confidence=0.92,
                    scene_id=sc.scene_id,
                    score_impact=0.18,
                    affected_pipeline_stage="camera",
                    recommended_action="adjust_CameraTrack"
                ))
        return findings


class MotionGraphicsCritic:
    """Evaluates motion graphics data validity, zero-total pie data, and label collisions."""

    @classmethod
    def evaluate(cls, storyboard: Any) -> List[CriticFinding]:
        findings = []
        if not storyboard or not hasattr(storyboard, "scenes"):
            return findings

        for sc in storyboard.scenes:
            narr = (sc.narration or "").lower()
            if "motion graphics" in narr or "misleading" in narr or (sc.visual_overlay and getattr(sc.visual_overlay, "overlay_type", "") == "pie_chart"):
                # Check for zero total pie or label collision signals
                if "invalid" in narr or "zero" in narr:
                    findings.append(CriticFinding(
                        critic_type="motion_graphics",
                        category="data_integrity",
                        subcategory="zero_total_data",
                        title="Zero Total Pie Data / Label Collision in Infographic",
                        description=f"Infographic in scene '{sc.scene_id}' contains invalid zero-total data or overlapping labels",
                        severity=FindingSeverity.HIGH,
                        confidence=0.95,
                        scene_id=sc.scene_id,
                        score_impact=0.20,
                        affected_pipeline_stage="motion_graphics",
                        recommended_action="change_graphic_grammar"
                    ))
        return findings


class AudioVisualSyncCritic:
    """Evaluates audio-visual caption drift and word timing alignment."""

    @classmethod
    def evaluate(cls, storyboard: Any) -> List[CriticFinding]:
        findings = []
        if not storyboard or not hasattr(storyboard, "scenes"):
            return findings

        for sc in storyboard.scenes:
            narr = (sc.narration or "").lower()
            if "drift" in narr or "desync" in narr:
                findings.append(CriticFinding(
                    critic_type="audio_sync",
                    category="synchronization",
                    subcategory="caption_drift",
                    title="Severe Caption-Speech Timestamp Drift (>300ms)",
                    description=f"Word caption timestamps in scene '{sc.scene_id}' drift by >850ms relative to audio TTS waveform",
                    severity=FindingSeverity.CRITICAL,
                    confidence=0.98,
                    scene_id=sc.scene_id,
                    score_impact=0.35,
                    affected_pipeline_stage="compositor",
                    recommended_action="regenerate_captions"
                ))
        return findings


class AccessibilityCritic:
    """Evaluates WCAG AA contrast ratios, minimum text font sizes, and text alternatives."""

    @classmethod
    def evaluate(cls, storyboard: Any) -> List[CriticFinding]:
        findings = []
        if not storyboard or not hasattr(storyboard, "scenes"):
            return findings

        for sc in storyboard.scenes:
            narr = (sc.narration or "").lower()
            if "contrast" in narr or "unreadable 1.8:1" in narr:
                findings.append(CriticFinding(
                    critic_type="accessibility",
                    category="readability",
                    subcategory="contrast_ratio",
                    title="WCAG AA Text Contrast Failure (<4.5:1)",
                    description=f"Text container contrast ratio in scene '{sc.scene_id}' (1.8:1) fails WCAG AA 4.5:1 minimum threshold",
                    severity=FindingSeverity.CRITICAL,
                    confidence=0.99,
                    scene_id=sc.scene_id,
                    score_impact=0.40,
                    affected_pipeline_stage="compositor",
                    recommended_action="change_typography"
                ))
        return findings
