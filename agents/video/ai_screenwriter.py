"""
AI Screenwriter (Phase 2 of VIDEO_PIPELINE_ARCHITECTURE_V2) -- LLM-powered script writer.

Replaces the deterministic template screenplay generator with real Groq-written
narration that flows as natural spoken speech.

The deterministic generator produced narration by splicing the raw user prompt into
fixed sentence templates ("Discover how {prompt} transforms outcomes."), which made
Edge-TTS read instruction-shaped text aloud verbatim. This module asks the LLM for
proper spoken narration instead, and hard-validates the result before accepting it --
if the model returns anything that still leaks the raw prompt or reads like a command,
the caller falls back to the (grammatically clean) deterministic path rather than
shipping broken narration.
"""
import re
import json
import logging
from typing import List, Optional, Any, Dict

from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


# ============================================================================
# PHASE 2 SCHEMA (per architecture spec)
# ============================================================================

class SceneScript(BaseModel):
    """One LLM-authored scene script."""
    scene_number: int
    narration_text: str
    on_screen_title: Optional[str] = None
    on_screen_stats: List[str] = Field(default_factory=list)
    visual_description: str = ""
    stock_search_queries: List[str] = Field(default_factory=list)
    transition_type: str = "crossfade"
    mood: str = "neutral"


# ============================================================================
# PROMPTS
# ============================================================================

SCREENWRITER_SYSTEM_PROMPT = """You are a professional video scriptwriter. Given a director's plan, write natural spoken narration for each scene.

Rules:
- Write as SPOKEN SPEECH, not written text (conversational, flowing)
- Each scene: 2-3 COMPLETE sentences. This is a strict requirement.
- Scene 1 (hook): Start with a compelling question or bold statement
- Connect each scene to the next with natural transitions
- Include specific on_screen_title (3-5 words, impactful)
- Include stock_search_queries that will find RELEVANT footage (be specific: "surgeon operating room technology" not "medical")
- NEVER include the raw user prompt in narration text
- NEVER start narration with "Generate" or "Create"
- NEVER refer to "this video", "this explainer", or the act of making a video. Talk about the SUBJECT itself.

CRITICAL -- narration length: each narration_text is read aloud by a text-to-speech
voice and must fill its scene's airtime. A single short clause leaves the scene silent
and sounds broken. The user message gives a target word count per scene: HIT IT.
Write full sentences with detail, not headlines or fragments.

WRONG (far too short, reads as a fragment): "AI helps doctors diagnose diseases"
RIGHT (complete, fills the airtime): "Artificial intelligence is already helping doctors spot conditions that once went unnoticed, catching subtle patterns in scans that the human eye can easily miss."

Output strict JSON (no markdown fences) shaped exactly like this example, and note how
long each narration_text actually is:
{"scenes": [{"scene_number": 1, "narration_text": "Every year, millions of diagnoses depend on a doctor catching a detail buried in a scan. What if technology could make sure nothing slips through?", "on_screen_title": "The Diagnostic Challenge", "on_screen_stats": ["1 in 20 cases missed"], "visual_description": "Radiologist reviewing scans on a bright display in a modern hospital", "stock_search_queries": ["radiologist reviewing medical scans", "hospital imaging department", "doctor analyzing x-ray screen"], "transition_type": "crossfade", "mood": "serious"}]}"""


# Narration must never begin with an instruction verb aimed at the AI.
_FORBIDDEN_NARRATION_STARTS = (
    "generate", "create", "make ", "produce", "build", "write ", "design", "craft",
)

# Phrases that mean the model is describing the deliverable instead of the subject.
_META_PHRASES = (
    "this video", "this explainer", "in this video", "our overview of",
    "this presentation", "this clip",
)

# Transition vocabulary understood by the renderer / ProducerService.normalize_transition
_TRANSITION_MAP = {
    "crossfade": "dissolve",
    "dissolve": "dissolve",
    "fade": "fade",
    "slide": "slide_left",
    "slide_left": "slide_left",
    "slide_right": "slide_right",
    "zoom": "zoom_in",
    "zoom_in": "zoom_in",
    "zoom_out": "zoom_out",
    "cut": "cut",
}


class AIScreenwriter:
    """
    LLM-powered screenplay generator (Phase 2).

    generate_scene_scripts() returns validated SceneScript objects, or None when the
    LLM is unavailable / returns unusable output -- callers must fall back.
    """

    # Terseness threshold for the pacing retry (not a rejection threshold).
    MIN_WORDS_PER_SCENE = 8
    # Hard ceiling: beyond this the model has ignored the brief and TTS would overrun the scene.
    MAX_WORDS_PER_SCENE = 60

    # Why the last generate_scene_scripts() call gave up, so the caller can log a
    # specific cause instead of a generic "fell back".
    last_failure_reason: str = "not attempted"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def generate_scene_scripts(
        cls,
        prompt: str,
        num_scenes: int,
        brief: Any = None,
        language: str = "en",
        llm_service: Optional[Any] = None,
    ) -> Optional[List[SceneScript]]:
        """
        Calls the LLM for `num_scenes` scene scripts. Returns None if unusable.
        """
        cls.last_failure_reason = "not attempted"

        if llm_service is None:
            try:
                from app.services.llm import LLMService
                llm_service = LLMService
            except Exception as e:
                cls.last_failure_reason = f"LLMService unavailable ({e})"
                logger.warning(f"AIScreenwriter: {cls.last_failure_reason} -- caller must fall back.")
                return None

        base_prompt = cls._build_user_prompt(prompt, num_scenes, brief, language)

        # Two attempts: the second one restates the exact-count requirement, which is the
        # most common reason a first response is unusable.
        for attempt in (1, 2):
            user_content = base_prompt
            if attempt == 2:
                user_content += (
                    f"\n\nIMPORTANT: Your previous response was rejected. Return EXACTLY "
                    f"{num_scenes} scene objects in the \"scenes\" array -- no more, no fewer. "
                    f"Narration must be plain spoken sentences about the subject only."
                )

            try:
                raw = llm_service.generate_json_advanced(
                    prompt=user_content,
                    system_prompt=SCREENWRITER_SYSTEM_PROMPT,
                    fallback_dict={},
                    temperature=0.7 if attempt == 1 else 0.4,
                    timeout=45.0,
                )
            except Exception as e:
                cls.last_failure_reason = f"LLM call raised {type(e).__name__}: {e}"
                logger.warning(f"AIScreenwriter: {cls.last_failure_reason} (attempt {attempt}).")
                continue

            scripts = cls._parse_response(raw)
            if not scripts:
                cls.last_failure_reason = (
                    "LLM returned no parseable scenes (empty/failed response -- "
                    "check the Groq error logged just above)"
                )
                logger.warning(f"AIScreenwriter: No parseable scenes on attempt {attempt}.")
                continue

            ok, reason = cls._validate_scripts(scripts, prompt)
            if not ok:
                cls.last_failure_reason = f"output rejected by validation ({reason})"
                logger.warning(f"AIScreenwriter: Output rejected by validation on attempt {attempt} ({reason}).")
                continue

            reconciled = cls._reconcile_scene_count(scripts, num_scenes)
            if reconciled is None:
                cls.last_failure_reason = (
                    f"LLM returned {len(scripts)} scenes but {num_scenes} are required"
                )
                logger.warning(f"AIScreenwriter: {cls.last_failure_reason} (attempt {attempt}).")
                continue

            # Terse narration is a pacing flaw, not a correctness one: worth one retry for
            # something better, but never worth falling back to the template over.
            quality = cls._quality_warnings(reconciled)
            if quality and attempt == 1:
                logger.info(f"AIScreenwriter: Retrying for better pacing ({'; '.join(quality)}).")
                continue
            if quality:
                logger.info(f"AIScreenwriter: Accepting script with pacing notes ({'; '.join(quality)}).")

            logger.info(
                f"AIScreenwriter: [OK] LLM generated {len(reconciled)} scene script(s) on attempt {attempt}. "
                f"First narration: '{reconciled[0].narration_text[:70]}...'"
            )
            return reconciled

        logger.warning("AIScreenwriter: All LLM attempts failed -- caller must fall back to deterministic script.")
        return None

    # ------------------------------------------------------------------
    # Prompt construction
    # ------------------------------------------------------------------

    # Approximate spoken delivery rate used to size narration to the scene's airtime.
    _WORDS_PER_SECOND = 2.5

    @classmethod
    def _build_user_prompt(cls, prompt: str, num_scenes: int, brief: Any, language: str) -> str:
        from agents.video import language as video_language
        lang = video_language.profile(language)

        lines = [
            f"Video topic (from the user): {prompt}",
            f"Write exactly {num_scenes} scenes.",
            f"Language for the narration: {lang.label} ({lang.code})",
        ]

        budget = None
        if brief is not None:
            title = getattr(brief, "project_title", None)
            tone = getattr(brief, "tone", None)
            audience = getattr(brief, "target_audience", None)
            core = getattr(brief, "core_message", None)
            structure = getattr(brief, "narrative_structure", None)
            budget = getattr(brief, "scene_duration_budget", None)

            if title:
                lines.append(f"Working title: {title}")
            if tone:
                lines.append(f"Tone: {tone}")
            if audience:
                lines.append(f"Target audience: {audience}")
            if core:
                lines.append(f"Core message: {core}")
            if structure is not None:
                lines.append(f"Narrative structure: {getattr(structure, 'value', structure)}")

        # When the AI Director authored a narrative arc, hand the screenwriter each beat's
        # purpose and key message -- that's what turns generic scenes into a real story.
        scene_plan = getattr(brief, "scene_plan", None) if brief is not None else None
        if scene_plan:
            lines.append("\nNarrative arc to follow, scene by scene:")
            for beat in list(scene_plan)[:num_scenes]:
                bits = [f"  Scene {beat.scene_number} [{beat.purpose}]"]
                if beat.mood:
                    bits.append(f"mood: {beat.mood}")
                if beat.key_message:
                    bits.append(f"message to convey: {beat.key_message}")
                lines.append(" | ".join(bits))
            lines.append(
                "Write each scene's narration so it delivers that scene's message in the "
                "director's intended mood, and flows into the next scene."
            )

        # Narration is spoken aloud, so its length must fill the scene's airtime -- too
        # short and the visual sits silent, too long and TTS stretches the whole video.
        if budget:
            per_scene = []
            for i, d in enumerate(list(budget)[:num_scenes], start=1):
                target_words = max(10, int(float(d) * cls._WORDS_PER_SECOND))
                per_scene.append(f"scene {i}: ~{target_words} words ({float(d):.1f}s)")
            lines.append(
                "Narration length per scene (this is spoken aloud, so match it closely): "
                + "; ".join(per_scene)
            )
        else:
            lines.append("Each scene's narration should be roughly 15-25 words.")

        # stock_search_queries feed Pexels and Openverse, whose catalogues are indexed
        # in English -- a French query returns a fraction of the results, and often the
        # wrong ones. The model happened to keep these English already, but "happened to"
        # is not a contract, so it is stated outright.
        if lang.code != "en":
            lines.append(
                f"LANGUAGE SPLIT -- this matters: write narration_text, on_screen_title and "
                f"on_screen_stats in {lang.label}, as a native speaker would phrase them. "
                f"But stock_search_queries and visual_description MUST stay in ENGLISH: they "
                f"are sent to stock-footage search engines that only index English, and a "
                f"{lang.label} query returns little or nothing usable."
            )

        lines.append(
            "Remember: narration is SPOKEN aloud by a text-to-speech voice. "
            "It must read like a human narrator talking about the subject -- never like "
            "an instruction, a title, or a description of the video itself. "
            "Write complete, flowing sentences, not fragments or headlines."
        )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Response parsing
    # ------------------------------------------------------------------

    @classmethod
    def _parse_response(cls, raw: Any) -> List[SceneScript]:
        """Tolerantly extracts SceneScript objects from whatever shape the LLM returned."""
        if not raw:
            return []

        # Some providers hand back a JSON string rather than a dict.
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                return []

        scene_dicts: List[Dict[str, Any]] = []
        if isinstance(raw, list):
            scene_dicts = [s for s in raw if isinstance(s, dict)]
        elif isinstance(raw, dict):
            for key in ("scenes", "scene_scripts", "script", "items", "data"):
                val = raw.get(key)
                if isinstance(val, list):
                    scene_dicts = [s for s in val if isinstance(s, dict)]
                    break
            else:
                # A single scene object returned bare.
                if "narration_text" in raw or "narration" in raw:
                    scene_dicts = [raw]

        scripts: List[SceneScript] = []
        for idx, sd in enumerate(scene_dicts):
            narration = (
                sd.get("narration_text")
                or sd.get("narration")
                or sd.get("text")
                or ""
            )
            if not isinstance(narration, str) or not narration.strip():
                continue

            stats = sd.get("on_screen_stats") or []
            if isinstance(stats, str):
                stats = [stats]
            queries = sd.get("stock_search_queries") or sd.get("search_queries") or []
            if isinstance(queries, str):
                queries = [queries]

            title = sd.get("on_screen_title") or sd.get("title")
            if title is not None and not isinstance(title, str):
                title = str(title)

            try:
                scripts.append(SceneScript(
                    scene_number=int(sd.get("scene_number", idx + 1) or idx + 1),
                    narration_text=cls._clean_text(narration),
                    on_screen_title=cls._clean_text(title) if title else None,
                    on_screen_stats=[cls._clean_text(str(s)) for s in stats if str(s).strip()][:3],
                    visual_description=cls._clean_text(str(sd.get("visual_description") or "")),
                    stock_search_queries=[cls._clean_text(str(q)) for q in queries if str(q).strip()][:3],
                    transition_type=str(sd.get("transition_type") or "crossfade").lower().strip(),
                    mood=str(sd.get("mood") or "neutral").lower().strip(),
                ))
            except Exception as e:
                logger.debug(f"AIScreenwriter: Skipping malformed scene {idx}: {e}")
                continue

        return scripts

    @staticmethod
    def _clean_text(text: str) -> str:
        """Strips markdown artifacts and collapses whitespace."""
        if not text:
            return ""
        cleaned = re.sub(r"[*_`#]+", "", str(text))
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    # ------------------------------------------------------------------
    # Validation gates
    # ------------------------------------------------------------------

    @classmethod
    def _validate_scripts(cls, scripts: List[SceneScript], original_prompt: str) -> tuple:
        """
        HARD correctness gates only. Returns (ok, reason).

        These catch narration that is genuinely broken to listen to -- raw prompt
        leakage, instruction-shaped text, meta commentary about the video itself.
        Failing here means falling back to the deterministic template, so length/pacing
        (a quality concern, handled separately in _quality_warnings) must NOT reject
        here: discarding seven good scenes because one is terse would ship strictly
        worse narration than it replaces.
        """
        if not scripts:
            return False, "no scenes parsed"

        prompt_norm = cls._normalize_for_compare(original_prompt)

        for s in scripts:
            narration = s.narration_text.strip()
            if not narration:
                return False, f"scene {s.scene_number} has empty narration"

            words = narration.split()
            if len(words) > cls.MAX_WORDS_PER_SCENE:
                return False, f"scene {s.scene_number} narration too long ({len(words)} words)"

            lower = narration.lower()
            if lower.startswith(_FORBIDDEN_NARRATION_STARTS):
                return False, f"scene {s.scene_number} narration starts with an instruction verb"

            for meta in _META_PHRASES:
                if meta in lower:
                    return False, f"scene {s.scene_number} narration contains meta phrase '{meta}'"

            # Raw-prompt leakage: reject if a long verbatim run of the prompt survives.
            if cls._contains_prompt_leak(narration, prompt_norm):
                return False, f"scene {s.scene_number} narration leaks the raw user prompt"

        return True, "ok"

    @classmethod
    def _quality_warnings(cls, scripts: List[SceneScript]) -> List[str]:
        """Non-blocking pacing observations, surfaced in logs for tuning."""
        warnings = []
        for s in scripts:
            n = len(s.narration_text.split())
            if n < cls.MIN_WORDS_PER_SCENE:
                warnings.append(f"scene {s.scene_number} is terse ({n} words)")
        return warnings

    @staticmethod
    def _normalize_for_compare(text: str) -> str:
        return re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower())

    @classmethod
    def _contains_prompt_leak(cls, narration: str, prompt_norm: str, window: int = 6) -> bool:
        """
        True when `window`+ consecutive words of the raw prompt appear verbatim in the
        narration -- the signature failure mode of the old template generator.
        """
        prompt_words = prompt_norm.split()
        if len(prompt_words) < window:
            return False
        narration_norm = cls._normalize_for_compare(narration)
        for i in range(len(prompt_words) - window + 1):
            chunk = " ".join(prompt_words[i:i + window])
            if chunk and chunk in narration_norm:
                return True
        return False

    # ------------------------------------------------------------------
    # Scene-count reconciliation
    # ------------------------------------------------------------------

    @classmethod
    def _reconcile_scene_count(cls, scripts: List[SceneScript], num_scenes: int) -> Optional[List[SceneScript]]:
        """
        The planning orchestrator hard-asserts len(screenplay.scenes) == recommended_scene_count,
        so the returned list must match exactly.

        Too many scenes -> keep the first N-1 plus the LAST one, preserving both the hook and
        the closing CTA rather than blindly truncating the ending away.
        Too few scenes -> return None; padding with filler would create duplicate/empty
        narration, so the caller retries or falls back instead.
        """
        scripts = sorted(scripts, key=lambda s: s.scene_number)

        if len(scripts) > num_scenes:
            logger.info(
                f"AIScreenwriter: LLM returned {len(scripts)} scenes, condensing to {num_scenes} "
                f"(keeping hook + closing scene)."
            )
            scripts = scripts[:num_scenes - 1] + [scripts[-1]] if num_scenes >= 2 else scripts[:1]
        elif len(scripts) < num_scenes:
            return None

        for i, s in enumerate(scripts):
            s.scene_number = i + 1
        return scripts

    # ------------------------------------------------------------------
    # Transition mapping
    # ------------------------------------------------------------------

    @classmethod
    def map_transition(cls, transition_type: str, scene_index: int = 0) -> str:
        """Maps the LLM's transition vocabulary onto renderer-supported styles."""
        key = (transition_type or "").lower().strip().replace("-", "_").replace(" ", "_")
        return _TRANSITION_MAP.get(key, "fade")
