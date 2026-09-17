"""
AI Director (Phase 1 of VIDEO_PIPELINE_ARCHITECTURE_V2) -- LLM-powered creative director.

Produces the narrative arc (hook -> problem -> solution -> proof -> cta) that the
AI Screenwriter then writes narration against, plus the palette / music / pacing
decisions for the whole video.

The deterministic director picked a structure by keyword-matching the prompt and split
the duration into equal slices, which gave every video the same shape regardless of
subject. This module asks the LLM to design the arc instead, and normalizes whatever it
returns so the planning invariants downstream still hold exactly.
"""
import re
import json
import logging
from typing import List, Optional, Any, Dict, Tuple

from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


# ============================================================================
# PHASE 1 SCHEMA (per architecture spec)
# ============================================================================

class DirectorScene(BaseModel):
    scene_number: int
    purpose: str = "body"
    mood: str = "neutral"
    visual_strategy: str = "stock_video"
    target_duration: float = 6.0
    key_message: str = ""
    uploaded_file_ref: Optional[str] = None


class VideoDirectorPlan(BaseModel):
    title: str
    narrative_arc: str = "hook-problem-solution-proof-cta"
    total_target_duration: float = 60.0
    color_palette: Dict[str, str] = Field(default_factory=dict)
    music_mood: str = "corporate_upbeat"
    tone: str = "Professional"
    target_audience: str = "General Audience"
    core_message: str = ""
    opening_hook: str = ""
    closing_message: str = ""
    call_to_action: str = ""
    scenes: List[DirectorScene] = Field(default_factory=list)


DIRECTOR_SYSTEM_PROMPT = """You are a professional video director. Given a user's topic and any uploaded files they've provided, create a structured video plan.

Rules:
- Always start with a HOOK scene (grab attention in first 3 seconds)
- Follow with PROBLEM -> SOLUTION -> PROOF -> CTA narrative arc
- Each scene: 5-12 seconds
- Total video duration must match the requested target
- If user uploaded videos, assign them to the most relevant scenes
- Choose visual_strategy: "user_upload" when a user file fits, "stock_video" for professional b-roll, "motion_graphic" for data/stats scenes
- key_message must be a concrete statement about the SUBJECT (what the viewer learns), never an instruction and never a description of the video itself
- title must be a real title for the subject, NOT the user's raw instruction text

Output strict JSON (no markdown fences) shaped exactly like this example:
{"title": "AI Revolution in Healthcare", "narrative_arc": "hook-problem-solution-proof-cta", "total_target_duration": 60, "color_palette": {"primary": "#1a1a2e", "accent": "#e94560", "text": "#ffffff"}, "music_mood": "corporate_upbeat", "tone": "Authoritative & Hopeful", "target_audience": "Healthcare professionals", "core_message": "AI is making diagnosis faster and more accurate", "opening_hook": "What if a machine could catch what a doctor misses?", "closing_message": "The future of medicine is already in the room.", "call_to_action": "See what AI can do for your practice.", "scenes": [{"scene_number": 1, "purpose": "hook", "mood": "intriguing", "visual_strategy": "stock_video", "target_duration": 7, "key_message": "Diagnostic errors affect millions of patients every year"}]}"""


# Valid narrative purposes; anything else is normalized to "body".
_VALID_PURPOSES = {"hook", "problem", "solution", "proof", "cta", "body", "intro", "conclusion"}

_FORBIDDEN_STARTS = ("generate", "create", "make ", "produce", "build", "write ", "design")
_META_PHRASES = ("this video", "this explainer", "in this video", "this presentation", "this clip")


class AIDirector:
    """
    LLM-powered director (Phase 1).

    generate_plan() returns a validated VideoDirectorPlan, or None when the LLM is
    unavailable / returns unusable output -- callers must fall back.
    """

    MIN_SCENES = 3
    MAX_SCENES = 10

    @classmethod
    def generate_plan(
        cls,
        prompt: str,
        target_duration: float,
        uploaded_files: Optional[List[str]] = None,
        llm_service: Optional[Any] = None,
        language: str = "en",
    ) -> Optional[VideoDirectorPlan]:
        """
        Design the narrative arc for one video.

        `language` decides what the viewer-facing copy is written in -- the title, core
        message, hook, closing line, CTA and every scene's key_message. It is threaded in
        here rather than left to the screenwriter downstream because the director is what
        actually shapes the story: a French video whose arc was conceived in English and
        translated one scene at a time reads like a translation, and the title (which the
        storyboard carries straight to the screen) would stay English outright.

        Machine-read fields stay English in every language -- see _build_user_prompt.
        """
        if llm_service is None:
            try:
                from app.services.llm import LLMService
                llm_service = LLMService
            except Exception as e:
                logger.warning(f"AIDirector: LLMService unavailable ({e}) -- caller must fall back.")
                return None

        user_content = cls._build_user_prompt(prompt, target_duration, uploaded_files, language)

        try:
            raw = llm_service.generate_json_advanced(
                prompt=user_content,
                system_prompt=DIRECTOR_SYSTEM_PROMPT,
                fallback_dict={},
                temperature=0.6,
                timeout=45.0,
            )
        except Exception as e:
            logger.warning(f"AIDirector: LLM call raised ({type(e).__name__}: {e}) -- caller must fall back.")
            return None

        plan = cls._parse_response(raw, target_duration)
        if plan is None:
            logger.warning("AIDirector: LLM returned no usable plan -- caller must fall back.")
            return None

        ok, reason = cls._validate_plan(plan, prompt)
        if not ok:
            logger.warning(f"AIDirector: Plan rejected by validation ({reason}) -- caller must fall back.")
            return None

        cls._normalize_durations(plan, target_duration)
        logger.info(
            f"AIDirector: [OK] Plan '{plan.title}' [lang={language}] -- {len(plan.scenes)} scenes, "
            f"arc=[{' -> '.join(s.purpose for s in plan.scenes)}]"
        )
        return plan

    # ------------------------------------------------------------------

    @classmethod
    def _build_user_prompt(cls, prompt: str, target_duration: float, uploaded_files: Optional[List[str]],
                           language: str = "en") -> str:
        approx_scenes = max(cls.MIN_SCENES, min(cls.MAX_SCENES, int(round(target_duration / 7.0))))
        lines = [
            f"Video topic (from the user): {prompt}",
            f"Target total duration: {target_duration:.0f} seconds",
            f"Plan approximately {approx_scenes} scenes (each 5-12 seconds), and make their "
            f"target_duration values sum to {target_duration:.0f} seconds.",
        ]
        if uploaded_files:
            lines.append(
                "The user uploaded these files -- assign each to the scene where it fits best "
                "using visual_strategy='user_upload' and uploaded_file_ref: "
                + ", ".join(uploaded_files)
            )
        else:
            lines.append("The user uploaded no files, so use 'stock_video' or 'motion_graphic' strategies only.")

        # Only the copy a viewer reads or hears is translated. purpose, visual_strategy,
        # narrative_arc, mood and music_mood are matched against English vocabularies
        # downstream (_VALID_PURPOSES here, the CC0 music-bed lookup in the audio stage),
        # so translating them would silently drop the video back to defaults.
        from agents.video import language as video_language
        lang = video_language.profile(language)
        if lang.code != "en":
            lines.append(
                f"\nWrite ALL viewer-facing copy in {lang.label} ({lang.code}): title, "
                f"core_message, opening_hook, closing_message, call_to_action, and every "
                f"scene's key_message. Write them the way a native speaker would, not as a "
                f"translation of English phrasing."
            )
            lines.append(
                "Keep these fields in ENGLISH regardless of the narration language, because "
                "they are machine-read and never shown to the viewer: purpose, visual_strategy, "
                "narrative_arc, mood, music_mood, tone, target_audience."
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------

    @classmethod
    def _parse_response(cls, raw: Any, target_duration: float) -> Optional[VideoDirectorPlan]:
        if not raw:
            return None
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                return None
        if not isinstance(raw, dict):
            return None

        scenes_raw = raw.get("scenes")
        if not isinstance(scenes_raw, list) or not scenes_raw:
            return None

        scenes: List[DirectorScene] = []
        for i, sd in enumerate(scenes_raw):
            if not isinstance(sd, dict):
                continue
            purpose = str(sd.get("purpose") or "body").lower().strip()
            if purpose not in _VALID_PURPOSES:
                purpose = "body"
            try:
                dur = float(sd.get("target_duration") or 6.0)
            except (TypeError, ValueError):
                dur = 6.0
            scenes.append(DirectorScene(
                scene_number=int(sd.get("scene_number", i + 1) or i + 1),
                purpose=purpose,
                mood=str(sd.get("mood") or "neutral").lower().strip(),
                visual_strategy=str(sd.get("visual_strategy") or "stock_video").lower().strip(),
                target_duration=max(1.0, dur),
                key_message=cls._clean(str(sd.get("key_message") or "")),
                uploaded_file_ref=sd.get("uploaded_file_ref") or None,
            ))

        if not scenes:
            return None

        scenes = sorted(scenes, key=lambda s: s.scene_number)
        if len(scenes) > cls.MAX_SCENES:
            scenes = scenes[:cls.MAX_SCENES - 1] + [scenes[-1]]
        for i, s in enumerate(scenes):
            s.scene_number = i + 1

        palette = raw.get("color_palette")
        if not isinstance(palette, dict):
            palette = {}

        try:
            return VideoDirectorPlan(
                title=cls._clean(str(raw.get("title") or "")) or "Untitled",
                narrative_arc=str(raw.get("narrative_arc") or "hook-problem-solution-proof-cta"),
                total_target_duration=float(raw.get("total_target_duration") or target_duration),
                color_palette={str(k): str(v) for k, v in palette.items()},
                music_mood=str(raw.get("music_mood") or "corporate_upbeat"),
                tone=cls._clean(str(raw.get("tone") or "Professional")),
                target_audience=cls._clean(str(raw.get("target_audience") or "General Audience")),
                core_message=cls._clean(str(raw.get("core_message") or "")),
                opening_hook=cls._clean(str(raw.get("opening_hook") or "")),
                closing_message=cls._clean(str(raw.get("closing_message") or "")),
                call_to_action=cls._clean(str(raw.get("call_to_action") or "")),
                scenes=scenes,
            )
        except Exception as e:
            logger.debug(f"AIDirector: Plan construction failed: {e}")
            return None

    @staticmethod
    def _clean(text: str) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", re.sub(r"[*_`#]+", "", str(text))).strip()

    # ------------------------------------------------------------------

    @classmethod
    def _validate_plan(cls, plan: VideoDirectorPlan, original_prompt: str) -> Tuple[bool, str]:
        """Hard gates: the plan's spoken-adjacent text must not leak the raw instruction."""
        if len(plan.scenes) < cls.MIN_SCENES:
            return False, f"only {len(plan.scenes)} scenes (min {cls.MIN_SCENES})"

        prompt_norm = re.sub(r"[^a-z0-9 ]+", " ", (original_prompt or "").lower())
        prompt_words = prompt_norm.split()

        for field_name in ("title", "opening_hook", "core_message", "closing_message"):
            value = getattr(plan, field_name, "") or ""
            lower = value.lower()
            if lower.startswith(_FORBIDDEN_STARTS):
                return False, f"{field_name} starts with an instruction verb"
            for meta in _META_PHRASES:
                if meta in lower:
                    return False, f"{field_name} contains meta phrase '{meta}'"
            if cls._leaks_prompt(value, prompt_words):
                return False, f"{field_name} leaks the raw user prompt"

        for s in plan.scenes:
            if cls._leaks_prompt(s.key_message, prompt_words):
                return False, f"scene {s.scene_number} key_message leaks the raw user prompt"

        return True, "ok"

    @staticmethod
    def _leaks_prompt(text: str, prompt_words: List[str], window: int = 6) -> bool:
        if not text or len(prompt_words) < window:
            return False
        norm = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
        for i in range(len(prompt_words) - window + 1):
            chunk = " ".join(prompt_words[i:i + window])
            if chunk and chunk in norm:
                return True
        return False

    # ------------------------------------------------------------------

    @classmethod
    def _normalize_durations(cls, plan: VideoDirectorPlan, target_duration: float) -> None:
        """
        Rescales scene durations so they sum exactly to the requested target.

        The planning orchestrator asserts sum(scene_duration_budget) == target within a
        1s tolerance, and LLM-proposed durations rarely add up on their own.
        """
        total = sum(s.target_duration for s in plan.scenes)
        if total <= 0:
            even = target_duration / max(len(plan.scenes), 1)
            for s in plan.scenes:
                s.target_duration = round(even, 2)
        else:
            scale = target_duration / total
            for s in plan.scenes:
                s.target_duration = round(max(1.0, s.target_duration * scale), 2)

        # Absorb rounding drift into the final scene so the sum is exact.
        drift = round(target_duration - sum(s.target_duration for s in plan.scenes), 2)
        if plan.scenes and abs(drift) >= 0.01:
            plan.scenes[-1].target_duration = round(max(1.0, plan.scenes[-1].target_duration + drift), 2)

        plan.total_target_duration = target_duration
