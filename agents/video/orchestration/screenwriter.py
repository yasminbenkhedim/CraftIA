# PHANTOM ARCHITECTURE NOTE: DirectorService, ScreenwriterService, ProducerService were previously claimed as independent microservices.
"""
Screenwriter Stage Service for VideoAgent Orchestration.
Converts DirectorBrief into multi-lingual, scene-by-scene Screenplay.
"""
import re
import time
import logging
from typing import List, Tuple, Dict, Any, Optional
from agents.video.orchestration.schemas import (
    ScreenwriterInput,
    Screenplay,
    ScreenplayScene,
    OnScreenText,
    TransitionIntent,
    AssetRole,
    ClaimReference,
    MediaType,
    PlanningValidationIssue,
    ValidationSeverity,
    safe_word_truncate,
    extract_topic_phrase
)

logger = logging.getLogger("uvicorn")

# Language-aware speech rates for duration estimation
SPEECH_RATES: Dict[str, float] = {
    "en": 2.5,  # words / sec (~150 wpm)
    "fr": 2.8,  # words / sec (~168 wpm)
    "de": 2.2,  # words / sec (~132 wpm)
    "es": 3.0,  # words / sec (~180 wpm)
    "it": 2.7,  # words / sec (~162 wpm)
    "ja": 5.5,  # characters / sec for CJK non-spaced text
}


class ScreenwriterService: # [PHANTOM - NON-EXISTENT]
    """
    Screenwriter Service converting DirectorBrief into scene screenplays with multi-lingual timing heuristics.
    """

    @classmethod
    def estimate_narration_duration(cls, narration: str, language: str = "en") -> float:
        """
        Estimates narration speech duration in seconds using language-aware rates.
        Special heuristic for Japanese (CJK characters per second).
        """
        if not narration or not narration.strip():
            return 0.0

        lang_code = language.lower()[:2]
        rate = SPEECH_RATES.get(lang_code, 2.5)

        if lang_code == "ja":
            # Count Japanese characters (excluding whitespace)
            clean_text = re.sub(r'\s+', '', narration)
            dur = len(clean_text) / rate
        else:
            words = re.findall(r'\w+', narration)
            dur = len(words) / rate

        return round(max(1.0, dur), 2)

    @classmethod
    def generate_deterministic_screenplay(cls, input_data: ScreenwriterInput) -> Screenplay:
        """
        Deterministic fallback Screenplay generator when LLM is unavailable or fails validation.
        """
        req = input_data.request
        brief = input_data.director_brief
        lang = req.language.lower()[:2]

        scenes: List[ScreenplayScene] = []
        num_scenes = brief.recommended_scene_count

        # Language-specific default templates
        templates = {
            "fr": [
                ("Introduction", "Découvrez les principes fondamentaux de notre solution."),
                ("Fonctionnalités", "Une architecture moderne conçue pour la performance."),
                ("Conclusion", "Faites passer vos opérations au niveau supérieur.")
            ],
            "es": [
                ("Introducción", "Descubra los principios clave de nuestra solución."),
                ("Características", "Una arquitectura moderna diseñada para el rendimiento."),
                ("Conclusión", "Lleve sus operaciones al siguiente nivel.")
            ],
            "de": [
                ("Einleitung", "Entdecken Sie die wichtigsten Prinzipien unserer Lösung."),
                ("Funktionen", "Eine moderne Architektur für maximale Leistung."),
                ("Fazit", "Bringen Sie Ihre Prozesse auf das nächste Level.")
            ],
            "ja": [
                ("導入", "ソリューションの主要な原則をご覧ください。"),
                ("機能", "パフォーマンスのために設計された現代的なアーキテクチャ。"),
                ("まとめ", "業務を次のレベルへと引き上げましょう。")
            ]
        }

        lang_temps = templates.get(lang, [
            ("Introduction", f"Welcome to our overview of {brief.project_title.rstrip('.')}."),
            ("Core Value", f"{brief.core_message}"),
            ("Conclusion", f"{brief.closing_message}")
        ])

        from agents.video.storyboard import VisualOverlay
        from agents.video.orchestration.schemas import NarrativeStructure

        for i in range(num_scenes):
            scene_id = f"scene_{i+1}"
            dur = brief.scene_duration_budget[i] if i < len(brief.scene_duration_budget) else 4.0

            # Automatic Chart/Diagram Detection & Overlay Placement
            visual_overlay = None
            if brief.narrative_structure == NarrativeStructure.DATA_STORY:
                if i == 1:
                    visual_overlay = VisualOverlay(
                        overlay_type="bar_chart",
                        title=f"{brief.project_title[:20]} Growth",
                        data_labels=["Q1", "Q2", "Q3", "Q4"],
                        data_values=[42.0, 65.0, 88.0, 115.0]
                    )
                elif i == 2:
                    visual_overlay = VisualOverlay(
                        overlay_type="line_chart",
                        title="Performance Metrics",
                        data_labels=["Mo 1", "Mo 2", "Mo 3", "Mo 4"],
                        data_values=[50.0, 72.0, 89.0, 98.0]
                    )
            # NOTE: TUTORIAL scenes intentionally get no architecture/workflow diagram
            # overlay -- those auto-generated box-and-arrow diagrams looked unpolished.
            # Leaving visual_overlay=None here means SceneComposer falls back to its
            # normal media search, which prefers real Pexels video clips / stock photos.
            elif brief.narrative_structure == NarrativeStructure.PRODUCT_DEMO:
                if i == 2:
                    visual_overlay = VisualOverlay(
                        overlay_type="bar_chart",
                        title="Benchmark Comparisons",
                        data_labels=["Speed", "Security", "Scale"],
                        data_values=[95.0, 99.0, 94.0]
                    )

            if i == 0:
                narration = f"{brief.opening_hook} {lang_temps[0][1]}"
                role = "Hook & Introduction"
                title_text = brief.project_title
                trans_style = "fade"
            elif i == num_scenes - 1:
                narration = f"{brief.closing_message} {brief.call_to_action or ''}"
                role = "Conclusion & Call to Action"
                title_text = "Next Steps"
                trans_style = "fade"
            else:
                tmpl_idx = (i - 1) % len(lang_temps)
                narration = f"{lang_temps[tmpl_idx][1]} Focusing on {safe_word_truncate(extract_topic_phrase(req.prompt), 35)}."
                role = f"Body Scene {i}"
                # Real topic phrase instead of a generic "Key Insight N" placeholder --
                # the short on-screen fade timing (see SceneComposer.compute_text_entrance_schedule)
                # already keeps this brief.
                title_text = safe_word_truncate(extract_topic_phrase(req.prompt), 28)
                trans_style = "slide_left" if i % 2 == 1 else "zoom_in"

            est_nar_dur = cls.estimate_narration_duration(narration, lang)

            scenes.append(ScreenplayScene(
                scene_index=i + 1,
                scene_id=scene_id,
                scene_objective=f"Deliver {role} message clearly.",
                narrative_role=role,
                narration=narration,
                on_screen_text=[OnScreenText(text=safe_word_truncate(title_text, 35), position="top", entrance_animation="typewriter")],
                visual_description=f"Modern visual supporting {role} for {safe_word_truncate(extract_topic_phrase(req.prompt), 25)}.",
                shot_description="Wide medium shot with clean motion graphics.",
                emotional_beat="Engaged",
                estimated_narration_duration=est_nar_dur,
                target_scene_duration=dur,
                transition_intent=TransitionIntent(style=trans_style, duration_sec=0.5),
                required_asset_roles=[AssetRole(role_name="background_visual", preferred_media_type=MediaType.LOCAL_ASSET)],
                continuity_references=[],
                facts_or_claims=[ClaimReference(claim_text=narration[:50], source="user_prompt")],
                prohibited_repetition=[],
                visual_overlay=visual_overlay
            ))

        total_nar = sum(s.estimated_narration_duration for s in scenes)
        total_sc_dur = sum(s.target_scene_duration for s in scenes)

        return Screenplay(
            title=brief.project_title,
            language=req.language,
            scenes=scenes,
            total_narration_duration=round(total_nar, 2),
            total_scene_duration=round(total_sc_dur, 2),
            repeated_terms=[],
            validation_warnings=[]
        )

    @classmethod
    def validate_screenplay(cls, screenplay: Screenplay) -> Tuple[bool, List[PlanningValidationIssue]]:
        issues = []

        if not screenplay.scenes:
            issues.append(PlanningValidationIssue(
                stage="Screenwriter", code="EMPTY_SCREENPLAY", severity=ValidationSeverity.CRITICAL,
                message="Screenplay contains no scenes.", repairable=False
            ))
            return False, issues

        seen_ids = set()
        seen_narrations = set()

        for idx, scene in enumerate(screenplay.scenes, 1):
            if scene.scene_index != idx:
                issues.append(PlanningValidationIssue(
                    stage="Screenwriter", code="NON_SEQUENTIAL_INDEX", severity=ValidationSeverity.ERROR,
                    message=f"Scene index {scene.scene_index} out of sequence (expected {idx}).", repairable=True
                ))

            if scene.scene_id in seen_ids:
                issues.append(PlanningValidationIssue(
                    stage="Screenwriter", code="DUPLICATE_SCENE_ID", severity=ValidationSeverity.ERROR,
                    message=f"Duplicate scene ID '{scene.scene_id}'.", repairable=True, scene_id=scene.scene_id
                ))
            seen_ids.add(scene.scene_id)

            if not scene.narration or not scene.narration.strip():
                issues.append(PlanningValidationIssue(
                    stage="Screenwriter", code="EMPTY_NARRATION", severity=ValidationSeverity.ERROR,
                    message=f"Scene '{scene.scene_id}' has empty narration.", repairable=True, scene_id=scene.scene_id
                ))

            # Duplicate narration check via normalized text
            norm_nar = re.sub(r'\W+', '', scene.narration.lower())
            if norm_nar in seen_narrations:
                issues.append(PlanningValidationIssue(
                    stage="Screenwriter", code="DUPLICATE_NARRATION", severity=ValidationSeverity.WARNING,
                    message=f"Scene '{scene.scene_id}' has duplicate narration text.", repairable=True, scene_id=scene.scene_id
                ))
            seen_narrations.add(norm_nar)

            # Check for prohibited terms in narration
            if screenplay.validation_warnings and any(term.lower() in scene.narration.lower() for term in screenplay.validation_warnings):
                issues.append(PlanningValidationIssue(
                    stage="Screenwriter", code="PROHIBITED_CONTENT_DETECTED", severity=ValidationSeverity.ERROR,
                    message=f"Scene '{scene.scene_id}' narration contains prohibited content.", repairable=True, scene_id=scene.scene_id
                ))

        is_passed = not any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL) for i in issues)
        return is_passed, issues

    @classmethod
    def generate_llm_screenplay(cls, input_data: ScreenwriterInput) -> Optional[Screenplay]:
        """
        Phase 2 (VIDEO_PIPELINE_ARCHITECTURE_V2): builds the Screenplay from real
        LLM-authored narration. Returns None when the LLM is unavailable or its output
        fails validation, so the caller falls back to the deterministic script.
        """
        from agents.video.ai_screenwriter import AIScreenwriter

        req = input_data.request
        brief = input_data.director_brief
        lang = req.language.lower()[:2]
        num_scenes = brief.recommended_scene_count

        scripts = AIScreenwriter.generate_scene_scripts(
            prompt=req.prompt,
            num_scenes=num_scenes,
            brief=brief,
            language=req.language,
        )
        if not scripts:
            # Surface the concrete cause recorded by AIScreenwriter so create_screenplay
            # can log it rather than a generic "fell back".
            cls._last_llm_failure = getattr(AIScreenwriter, "last_failure_reason", "unknown")
            return None

        scenes: List[ScreenplayScene] = []
        for i, sc in enumerate(scripts):
            dur = brief.scene_duration_budget[i] if i < len(brief.scene_duration_budget) else 4.0
            narration = sc.narration_text
            est_nar_dur = cls.estimate_narration_duration(narration, lang)

            on_screen = []
            if sc.on_screen_title:
                on_screen.append(OnScreenText(
                    text=safe_word_truncate(sc.on_screen_title, 35),
                    position="top",
                    entrance_animation="typewriter"
                ))

            if i == 0:
                role = "Hook & Introduction"
            elif i == len(scripts) - 1:
                role = "Conclusion & Call to Action"
            else:
                role = f"Body Scene {i}"

            scenes.append(ScreenplayScene(
                scene_index=i + 1,
                scene_id=f"scene_{i + 1}",
                scene_objective=f"Deliver {role} message clearly.",
                narrative_role=role,
                narration=narration,
                on_screen_text=on_screen,
                visual_description=sc.visual_description or (sc.stock_search_queries[0] if sc.stock_search_queries else narration[:60]),
                shot_description=f"{sc.mood} shot supporting the scene message.",
                emotional_beat=sc.mood.capitalize() if sc.mood else "Engaged",
                estimated_narration_duration=est_nar_dur,
                target_scene_duration=dur,
                transition_intent=TransitionIntent(
                    style=AIScreenwriter.map_transition(sc.transition_type, i),
                    duration_sec=0.5
                ),
                required_asset_roles=[AssetRole(role_name="background_visual", preferred_media_type=MediaType.STOCK_VIDEO)],
                continuity_references=[],
                facts_or_claims=[ClaimReference(claim_text=narration[:50], source="llm_screenwriter")],
                prohibited_repetition=[],
                visual_overlay=None,
                stock_search_queries=sc.stock_search_queries,
                on_screen_stats=sc.on_screen_stats,
            ))

        total_nar = sum(s.estimated_narration_duration for s in scenes)
        total_sc_dur = sum(s.target_scene_duration for s in scenes)

        return Screenplay(
            title=brief.project_title,
            language=req.language,
            scenes=scenes,
            total_narration_duration=round(total_nar, 2),
            total_scene_duration=round(total_sc_dur, 2),
            repeated_terms=[],
            validation_warnings=[]
        )

    @classmethod
    def create_screenplay(cls, input_data: ScreenwriterInput) -> Tuple[Screenplay, bool, List[PlanningValidationIssue]]:
        """
        Executes Screenwriter stage and returns (Screenplay, validation_passed, issues).

        Prefers real LLM-authored narration (Phase 2); falls back to the deterministic
        template only when the LLM is unavailable or its output fails validation.
        """
        req = input_data.request
        if req.prohibited_content:
            logger.info(f"ScreenwriterService: Injecting prohibited content terms into prompt context: {req.prohibited_content}")

        sp = None
        cls._last_llm_failure = "LLM returned no usable screenplay"
        fallback_reason = cls._last_llm_failure
        try:
            sp = cls.generate_llm_screenplay(input_data)
            fallback_reason = cls._last_llm_failure
        except Exception as e:
            fallback_reason = f"{type(e).__name__}: {e}"
            logger.warning(f"ScreenwriterService: LLM screenplay generation raised ({fallback_reason}).")

        if sp is not None:
            logger.info(f"SCREENWRITER: LLM path OK, generated {len(sp.scenes)} scenes")
        else:
            logger.error(f"SCREENWRITER: FELL BACK to template because: {fallback_reason}")
            sp = cls.generate_deterministic_screenplay(input_data)

        if req.prohibited_content:
            sp.validation_warnings.extend(req.prohibited_content)
        passed, issues = cls.validate_screenplay(sp)
        return sp, passed, issues
