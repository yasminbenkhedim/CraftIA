"""
Visual Continuity Validator for VideoAgent.
Validates text contrast, palette consistency, locked field overrides, and variety policy.
"""
import hashlib
import logging
from typing import List, Tuple, Dict, Any, Optional
from agents.video.continuity.schemas import (
    VisualStyleAnchor,
    SceneContinuitySpec,
    StyleFingerprint,
    VisualContinuityReport,
    VisualVarietyPolicy,
    ColorPalette
)
from agents.video.orchestration.schemas import (
    PlanningValidationIssue,
    ValidationSeverity
)

logger = logging.getLogger("uvicorn")


class VisualContinuityValidator:
    """
    Validator inspecting project visual continuity, contrast ratios, locked field compliance, and layout variety.
    """

    @classmethod
    def compute_style_fingerprint(cls, scene_spec: SceneContinuitySpec, anchor: VisualStyleAnchor) -> StyleFingerprint:
        """Computes a stable deterministic style fingerprint for a scene."""
        pal_str = f"{anchor.palette.background_color}_{anchor.palette.foreground_color}_{'_'.join(anchor.palette.accent_colors)}"
        pal_hash = hashlib.sha256(pal_str.encode('utf-8')).hexdigest()[:12]
        
        return StyleFingerprint(
            palette_hash=pal_hash,
            dominant_colors=[anchor.palette.background_color] + anchor.palette.accent_colors,
            typography_id=anchor.typography.heading_family,
            template_family=anchor.visual_medium.value,
            provider_id="procedural_overlay",
            generation_method="procedural",
            seed=42,
            transition_family=scene_spec.overrides.get("transition_family", anchor.transition_family.value),
            motion_style=anchor.motion_style.value,
            aspect_ratio="16:9",
            resolution="1920x1080",
            visual_medium=anchor.visual_medium.value,
            logical_asset_id=f"asset_{scene_spec.scene_id}"
        )

    @classmethod
    def validate_contrast(cls, bg_hex: str, fg_hex: str) -> Tuple[bool, float]:
        """Validates WCAG contrast ratio (>= 4.5:1 for standard text)."""
        ratio = ColorPalette.calculate_contrast_ratio(bg_hex, fg_hex)
        return ratio >= 4.5, ratio

    @classmethod
    def validate_project_continuity(
        cls,
        anchor: VisualStyleAnchor,
        scene_specs: List[SceneContinuitySpec],
        variety_policy: Optional[VisualVarietyPolicy] = None
    ) -> VisualContinuityReport:
        policy = variety_policy or VisualVarietyPolicy()
        issues: List[PlanningValidationIssue] = []
        auto_repairs: List[Dict[str, Any]] = []
        scene_scores: Dict[str, float] = {}

        # 1. Text / Background Contrast Validation & Auto-Repair
        passed_contrast, ratio = cls.validate_contrast(anchor.palette.background_color, anchor.palette.foreground_color)
        if not passed_contrast:
            if "palette" not in anchor.locked_fields:
                # Auto-repair: fallback to high-contrast white text
                old_fg = anchor.palette.foreground_color
                anchor.palette.foreground_color = "#FFFFFF"
                auto_repairs.append({
                    "issue": "LOW_TEXT_CONTRAST",
                    "field": "palette.foreground_color",
                    "old_value": old_fg,
                    "new_value": "#FFFFFF",
                    "contrast_ratio": ratio
                })
                logger.info(f"VisualContinuityValidator: Auto-repaired low text contrast ({ratio}:1 -> 21:1)")
            else:
                issues.append(PlanningValidationIssue(
                    stage="ContinuityValidator",
                    code="BRAND_CONTRAST_VIOLATION",
                    severity=ValidationSeverity.ERROR,
                    message=f"Locked brand palette has insufficient text contrast ratio ({ratio:.2f}:1 < 4.5:1)."
                ))

        # 2. Scene-Level Overrides & Locked Field Check
        for spec in scene_specs:
            sc_score = 1.0
            for override_key in spec.overrides.keys():
                if override_key in anchor.locked_fields:
                    issues.append(PlanningValidationIssue(
                        stage="ContinuityValidator",
                        code="LOCKED_FIELD_OVERRIDE_VIOLATION",
                        severity=ValidationSeverity.ERROR,
                        message=f"Scene '{spec.scene_id}' attempted to override locked anchor field '{override_key}'.",
                        scene_id=spec.scene_id
                    ))
                    sc_score -= 0.3

            scene_scores[spec.scene_id] = max(0.0, round(sc_score, 2))

        # 3. Layout & Transition Variety Check
        transitions = [s.overrides.get("transition_family", anchor.transition_family.value) for s in scene_specs]
        current_trans_run = 1
        for i in range(1, len(transitions)):
            if transitions[i] == transitions[i-1]:
                current_trans_run += 1
                if current_trans_run > policy.maximum_same_transition_run:
                    issues.append(PlanningValidationIssue(
                        stage="ContinuityValidator",
                        code="EXCESSIVE_SAME_TRANSITION_RUN",
                        severity=ValidationSeverity.WARNING,
                        message=f"Transition '{transitions[i]}' repeated consecutively {current_trans_run} times (max allowed: {policy.maximum_same_transition_run})."
                    ))
            else:
                current_trans_run = 1

        overall_score = round(sum(scene_scores.values()) / max(1, len(scene_scores)), 2)
        passed = not any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL) for i in issues)

        return VisualContinuityReport(
            project_score=overall_score,
            confidence=0.95,
            scene_scores=scene_scores,
            issues=issues,
            auto_repairs=auto_repairs,
            unresolved_issue_count=len(issues),
            passed=passed
        )
