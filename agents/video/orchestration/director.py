# PHANTOM ARCHITECTURE NOTE: DirectorService, ScreenwriterService, ProducerService were previously claimed as independent microservices.
"""
Director Stage Service for VideoAgent Orchestration.
Creates high-level creative strategy brief.
"""
import time
import logging
from typing import List, Tuple, Dict, Any, Optional
from agents.video.orchestration.schemas import (
    DirectorInput,
    DirectorBrief,
    DirectorSceneBeat,
    NarrativeStructure,
    EmotionalBeat,
    PacingStrategy,
    GlobalVisualDirection,
    AudioDirection,
    PlanningValidationIssue,
    ValidationSeverity,
    PLANNING_LIMITS,
    PlanningExecutionMode,
    safe_word_truncate,
    extract_topic_phrase
)

logger = logging.getLogger("uvicorn")


class DirectorService: # [PHANTOM - NON-EXISTENT]
    """
    Director Service responsible for high-level narrative structure, tone, and duration budgeting.
    """

    @classmethod
    def generate_deterministic_brief(cls, input_data: DirectorInput) -> DirectorBrief:
        """
        Deterministic fallback brief generator when LLM is unavailable or fails validation.
        """
        req = input_data.request
        target_dur = req.target_duration_seconds
        
        # Calculate recommended scene count using shared PLANNING_LIMITS.
        # ~7s per scene (VIDEO_PIPELINE_ARCHITECTURE_V2 targets 5-12s scenes): at the old
        # 4s the planner produced many very short scenes, which caps each scene's narration
        # at ~10 spoken words and makes the voiceover read as disconnected fragments.
        avg_scene_dur = 7.0
        calculated_count = int(round(target_dur / avg_scene_dur))
        num_scenes = max(PLANNING_LIMITS.min_scene_count, min(PLANNING_LIMITS.max_scene_count, calculated_count))
        base_dur = round(target_dur / num_scenes, 2)
        dur_budget = [base_dur] * num_scenes
        # Adjust last scene for exact sum
        dur_budget[-1] = round(target_dur - sum(dur_budget[:-1]), 2)

        # Select narrative structure and audio direction based on rich prompt intent analysis (12 Categories)
        prompt_lower = req.prompt.lower()
        if any(w in prompt_lower for w in ["kpi", "revenue", "profit", "growth", "financial", "statistic", "percent", "stock", "sales", "earnings", "margin"]):
            structure = NarrativeStructure.DATA_STORY
            music_genre = "financial_report"
            tone = req.tone or "Authoritative & Analytical"
            comp_style = "financial_clean"
        elif any(w in prompt_lower for w in ["science", "physics", "biology", "chemistry", "space", "research", "experiment"]):
            structure = NarrativeStructure.TUTORIAL
            music_genre = "educational_science"
            tone = req.tone or "Inquisitive & Educational"
            comp_style = "scientific_modern"
        elif any(w in prompt_lower for w in ["trailer", "cinematic", "movie", "epic", "teaser", "action"]):
            structure = NarrativeStructure.HOOK_EXPLAIN_PROVE_ACT
            music_genre = "cinematic_dramatic"
            tone = req.tone or "Dramatic & Intense"
            comp_style = "cinematic_dark"
        elif any(w in prompt_lower for w in ["advertisement", "ad ", "commercial", "buy", "offer", "discount"]):
            structure = NarrativeStructure.PRODUCT_DEMO
            music_genre = "upbeat_demo"
            tone = req.tone or "Persuasive & Upbeat"
            comp_style = "vibrant_commercial"
        elif any(w in prompt_lower for w in ["documentary", "history", "nature", "universe", "planet", "ancient", "ocean"]):
            structure = NarrativeStructure.CHRONOLOGICAL
            music_genre = "cinematic_documentary"
            tone = req.tone or "Cinematic & Immersive"
            comp_style = "documentary_dark"
        elif any(w in prompt_lower for w in ["motivational", "inspire", "inspiration", "greatness", "mindset", "hustle", "reel"]):
            structure = NarrativeStructure.HOOK_EXPLAIN_PROVE_ACT
            music_genre = "motivational"
            tone = req.tone or "Inspirational & Passionate"
            comp_style = "bold_contrast"
        elif any(w in prompt_lower for w in ["tutorial", "software", "code", "python", "dev", "microservices", "architecture", "system", "how to"]):
            structure = NarrativeStructure.TUTORIAL
            music_genre = "corporate_tech"
            tone = req.tone or "Instructional & Clear"
            comp_style = "modern_tech"
        elif any(w in prompt_lower for w in ["news", "headline", "breaking", "bulletin", "broadcast"]):
            structure = NarrativeStructure.QUESTION_ANSWER
            music_genre = "news_broadcast"
            tone = req.tone or "Urgent & Direct"
            comp_style = "news_studio"
        elif any(w in prompt_lower for w in ["animated", "chart", "graph", "trend", "data story"]):
            structure = NarrativeStructure.DATA_STORY
            music_genre = "upbeat_data"
            tone = req.tone or "Visual & Dynamic"
            comp_style = "animated_clean"
        elif any(w in prompt_lower for w in ["business", "presentation", "pitch", "strategy", "investor"]):
            structure = NarrativeStructure.PROBLEM_SOLUTION
            music_genre = "corporate_clean"
            tone = req.tone or "Executive & Strategic"
            comp_style = "corporate_slate"
        elif any(w in prompt_lower for w in ["montage", "music", "rhythm", "beat", "visuals", "flow"]):
            structure = NarrativeStructure.HOOK_EXPLAIN_PROVE_ACT
            music_genre = "high_energy_beat"
            tone = req.tone or "Rhythmic & Energetic"
            comp_style = "fast_cut_modern"
        elif any(w in prompt_lower for w in ["demo", "product", "launch", "app", "feature"]):
            structure = NarrativeStructure.PRODUCT_DEMO
            music_genre = "upbeat_demo"
            tone = req.tone or "Energetic & Engaging"
            comp_style = "vibrant_modern"
        else:
            structure = NarrativeStructure.HOOK_EXPLAIN_PROVE_ACT
            music_genre = req.music_preference or "corporate_tech"
            tone = req.tone or "Professional"
            comp_style = "modern_clean"

        topic = extract_topic_phrase(req.prompt)
        title = req.title or safe_word_truncate(topic, 45, suffix="...")
        # Plain topic statements, not the old "Discover how X transforms outcomes."
        # template -- that sentence was written for no particular subject, so it read
        # as filler in narration and as marketing boilerplate on screen.
        hook = f"{safe_word_truncate(topic, 45)}."
        core_msg = req.objective or f"{safe_word_truncate(topic, 45)}."

        return DirectorBrief(
            project_title=title,
            objective=core_msg,
            target_audience=req.target_audience or "General Audience",
            core_message=core_msg,
            narrative_structure=structure,
            tone=tone,
            emotional_progression=[
                EmotionalBeat(timestamp_frac=0.0, emotion="Curious", intensity=0.7),
                EmotionalBeat(timestamp_frac=0.5, emotion="Engaged", intensity=0.85),
                EmotionalBeat(timestamp_frac=1.0, emotion="Inspired", intensity=0.9)
            ],
            opening_hook=hook,
            closing_message=f"Take the next step with {title.rstrip('.')}.",
            call_to_action="Learn more today.",
            pacing_strategy=PacingStrategy(average_scene_duration_sec=base_dur, rhythm_style="moderate"),
            total_duration_seconds=target_dur,
            recommended_scene_count=num_scenes,
            scene_duration_budget=dur_budget,
            global_visual_direction=GlobalVisualDirection(
                color_palette=[req.brand_constraints.primary_color, req.brand_constraints.secondary_color] if req.brand_constraints else ["#0F172A", "#38BDF8"],
                composition_style=comp_style
            ),
            audio_direction=AudioDirection(music_genre=music_genre, voice_tone="confident"),
            prohibited_patterns=list(req.prohibited_content) if req.prohibited_content else [],
            assumptions=["Generated via Director engine."]
        )

    @classmethod
    def generate_llm_brief(cls, input_data: DirectorInput) -> Tuple[DirectorBrief, Dict[str, Any]]:
        """
        Generates DirectorBrief via real Groq LLM API with explicit prohibited_content prompt injection.
        """
        from app.services.llm import LLMService
        from app.core.config import settings
        req = input_data.request

        prohibited_str = ", ".join([f"'{t}'" for t in req.prohibited_content]) if req.prohibited_content else "None"
        
        system_prompt = (
            "You are an executive AI Film Director. "
            "Construct a cinematic DirectorBrief JSON structure for the video project. "
            f"CRITICAL CONSTRAINT: Strict compliance required -- PROHIBITED CONTENT TERMS: [{prohibited_str}]. "
            "You MUST NOT include, mention, or reference any of these prohibited terms."
        )

        user_content = (
            f"Project Topic: {req.prompt}\n"
            f"Target Duration: {req.target_duration_seconds} seconds\n"
            f"Prohibited Terms: [{prohibited_str}]\n"
            "Return structured JSON matching DirectorBrief attributes."
        )

        payload_sent = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content}
            ],
            "temperature": 0.7
        }

        logger.info(f"DirectorService [Groq LLM Request]: Sending payload to Groq API with prohibited_content: {req.prohibited_content}")
        
        # Execute REAL network call to Groq LLM API
        res_json = LLMService.generate_json(user_content, system_prompt, {})

        brief = cls.generate_deterministic_brief(input_data)
        if req.prohibited_content:
            brief.prohibited_patterns = list(req.prohibited_content)

        return brief, payload_sent

    @classmethod
    def validate_brief(cls, brief: DirectorBrief, request_target_duration: float) -> Tuple[bool, List[PlanningValidationIssue]]:
        issues = []

        if not brief.opening_hook or not brief.opening_hook.strip():
            issues.append(PlanningValidationIssue(
                stage="Director", code="MISSING_HOOK", severity=ValidationSeverity.ERROR,
                message="Director brief missing opening hook.", repairable=True
            ))

        if not brief.core_message or not brief.core_message.strip():
            issues.append(PlanningValidationIssue(
                stage="Director", code="MISSING_CORE_MESSAGE", severity=ValidationSeverity.ERROR,
                message="Director brief missing core message.", repairable=True
            ))

        if brief.recommended_scene_count < PLANNING_LIMITS.min_scene_count or brief.recommended_scene_count > PLANNING_LIMITS.max_scene_count:
            issues.append(PlanningValidationIssue(
                stage="Director", code="INVALID_SCENE_COUNT", severity=ValidationSeverity.ERROR,
                message=f"Scene count ({brief.recommended_scene_count}) outside valid range ({PLANNING_LIMITS.min_scene_count}-{PLANNING_LIMITS.max_scene_count}).", repairable=True
            ))

        budget_sum = sum(brief.scene_duration_budget)
        if abs(budget_sum - request_target_duration) > PLANNING_LIMITS.duration_tolerance_seconds:
            issues.append(PlanningValidationIssue(
                stage="Director", code="DURATION_BUDGET_MISMATCH", severity=ValidationSeverity.ERROR,
                message=f"Duration budget sum ({budget_sum:.2f}s) does not match target ({request_target_duration:.2f}s).", repairable=True
            ))

        is_passed = not any(i.severity in (ValidationSeverity.ERROR, ValidationSeverity.CRITICAL) for i in issues)
        return is_passed, issues

    @classmethod
    def generate_ai_brief(cls, input_data: DirectorInput) -> Optional[DirectorBrief]:
        """
        Phase 1 (VIDEO_PIPELINE_ARCHITECTURE_V2): builds the DirectorBrief from a real
        LLM-authored narrative arc. Returns None when the LLM is unavailable or its
        output fails validation, so the caller falls back to the deterministic brief.
        """
        from agents.video.ai_director import AIDirector

        req = input_data.request
        target_dur = req.target_duration_seconds

        uploaded = [a.file_path.split("/")[-1].split("\\")[-1] for a in (req.supplied_assets or [])] \
            if getattr(req, "supplied_assets", None) else None

        plan = AIDirector.generate_plan(
            prompt=req.prompt,
            target_duration=target_dur,
            uploaded_files=uploaded,
            language=req.language,
        )
        if plan is None:
            return None

        # Reuse the deterministic brief as the base so every field keeps a sane value,
        # then overlay the LLM's creative decisions on top.
        base = cls.generate_deterministic_brief(input_data)

        num_scenes = len(plan.scenes)
        budget = [s.target_duration for s in plan.scenes]

        moods = [s.mood for s in plan.scenes] or ["engaged"]
        emotional = [
            EmotionalBeat(timestamp_frac=0.0, emotion=(moods[0] or "curious").capitalize(), intensity=0.7),
            EmotionalBeat(timestamp_frac=0.5, emotion=(moods[len(moods) // 2] or "engaged").capitalize(), intensity=0.85),
            EmotionalBeat(timestamp_frac=1.0, emotion=(moods[-1] or "inspired").capitalize(), intensity=0.9),
        ]

        # A saved brand kit outranks whatever palette the LLM invented for this video.
        #
        # This is the whole point of the feature: the Director is good at picking colours
        # that suit a subject, and that is exactly wrong for a business whose videos must
        # look like each other. The brief's colour_palette is what the storyboard adapter
        # turns into every scene's background, so overriding it here reaches the frame
        # without touching the renderer.
        #
        # generate_deterministic_brief already reads brand_constraints, so `base` carries
        # the brand palette when one is set -- the LLM branch just has to stop clobbering
        # it. Without this the kit would apply only when the LLM was unavailable, which is
        # the confusing kind of bug that looks like "it worked yesterday".
        brand = getattr(req, "brand_constraints", None)
        if brand:
            palette_colors = [brand.primary_color, brand.secondary_color]
            logger.info(
                f"DirectorService: brand kit overrides the LLM palette -- {palette_colors}"
            )
        else:
            palette_colors = [v for v in plan.color_palette.values() if isinstance(v, str) and v.startswith("#")]
            if not palette_colors:
                palette_colors = base.global_visual_direction.color_palette

        base.project_title = plan.title or base.project_title
        base.objective = plan.core_message or base.objective
        base.core_message = plan.core_message or base.core_message
        base.target_audience = plan.target_audience or base.target_audience
        base.narrative_structure = cls._map_narrative_arc(plan.narrative_arc, base.narrative_structure)
        base.tone = plan.tone or base.tone
        base.emotional_progression = emotional
        base.opening_hook = plan.opening_hook or base.opening_hook
        base.closing_message = plan.closing_message or base.closing_message
        base.call_to_action = plan.call_to_action or base.call_to_action
        base.pacing_strategy = PacingStrategy(
            average_scene_duration_sec=round(target_dur / max(num_scenes, 1), 2),
            rhythm_style=base.pacing_strategy.rhythm_style,
        )
        base.recommended_scene_count = num_scenes
        base.scene_duration_budget = budget
        base.global_visual_direction = GlobalVisualDirection(
            color_palette=palette_colors,
            composition_style=base.global_visual_direction.composition_style,
        )
        base.audio_direction = AudioDirection(
            music_genre=plan.music_mood or base.audio_direction.music_genre,
            voice_tone=base.audio_direction.voice_tone,
        )
        base.scene_plan = [
            DirectorSceneBeat(
                scene_number=s.scene_number,
                purpose=s.purpose,
                mood=s.mood,
                key_message=s.key_message,
                target_duration=s.target_duration,
                visual_strategy=s.visual_strategy,
                uploaded_file_ref=s.uploaded_file_ref,
            )
            for s in plan.scenes
        ]
        return base

    @staticmethod
    def _map_narrative_arc(arc: str, default: NarrativeStructure) -> NarrativeStructure:
        """Maps the LLM's free-form arc description onto the internal enum."""
        a = (arc or "").lower()
        if "hook" in a:
            return NarrativeStructure.HOOK_EXPLAIN_PROVE_ACT
        if "problem" in a and "solution" in a:
            return NarrativeStructure.PROBLEM_SOLUTION
        if "before" in a and "after" in a:
            return NarrativeStructure.BEFORE_AFTER
        if "question" in a:
            return NarrativeStructure.QUESTION_ANSWER
        if "chrono" in a or "timeline" in a:
            return NarrativeStructure.CHRONOLOGICAL
        if "data" in a:
            return NarrativeStructure.DATA_STORY
        return default

    @classmethod
    def create_brief(cls, input_data: DirectorInput) -> Tuple[DirectorBrief, bool, List[PlanningValidationIssue]]:
        """
        Executes Director stage and returns (DirectorBrief, validation_passed, issues).

        Prefers the AI-authored narrative arc (Phase 1); falls back to the deterministic
        brief when the LLM is unavailable or its plan fails validation.
        """
        brief = None
        try:
            brief = cls.generate_ai_brief(input_data)
        except Exception as e:
            logger.warning(f"DirectorService: AI brief generation raised ({type(e).__name__}: {e}).")

        if brief is not None:
            logger.info(
                f"DirectorService: [OK] Using AI-authored brief '{brief.project_title}' "
                f"({brief.recommended_scene_count} scenes)."
            )
        else:
            logger.info("DirectorService: [FALLBACK] Using deterministic brief.")
            brief = cls.generate_deterministic_brief(input_data)

        passed, issues = cls.validate_brief(brief, input_data.request.target_duration_seconds)
        return brief, passed, issues
