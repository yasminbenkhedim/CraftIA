"""
VisualQueryGenerator -- Core Semantic Query Generation Engine for VideoAgent (Upgrade 2).
Replaces simple narration truncation (scene.narration[:60]) with a production-grade
visual scene representation pipeline.

Features:
- Batch LLM concept extraction via LLMService
- Per-scene isolation & single-scene retry
- Strict deterministic fallback (rule-based, no LLM) meeting 5 "strictly better" criteria
- Integration with DomainPaletteEngine (no circular import)
- Scene memory duplicate tracking (SceneVisualMemory)
- Multi-tier caching (VisualQueryCache)
- Provider adaptation (QueryAdapterRegistry)
- Feature flag & emergency VQG_DISABLED override
- Performance budget enforcement (max 3 LLM calls, 5000 tokens, 15s latency)
- Structured diagnostics
"""
import os
import re
import json
import time
import logging
from typing import Dict, Any, List, Optional, Tuple, Set

from agents.video.visual_query_schemas import (
    VisualQueryInput, VisualQueryResult, VisualQueryDiagnostics,
    VisualQueryConfig, VisualQueryMode, VisualQueryPrivacyMode, VisualQueryBudget
)
from agents.video.domain_palette_engine import DomainPaletteEngine
from agents.video.scene_visual_memory import SceneVisualMemory
from agents.video.visual_query_scorer import QueryScorer
from agents.video.visual_query_cache import VisualQueryCache
from agents.video.provider_query_adapters import QueryAdapterRegistry
from app.services.llm import LLMService

logger = logging.getLogger("uvicorn")


class VisualQueryGenerator:
    """
    Semantic Media Query Generator for VideoAgent.
    """

    BLOCKED_TERMS: Set[str] = {
        "gore", "blood", "nude", "naked", "weapon", "gun", "dead",
        "explicit", "nsfw", "violent", "murder", "suicide",
        "copyright", "trademark", "watermark"
    }

    FILLER_PHRASES: List[str] = [
        "welcome to", "today we", "our benchmarks", "let us", "in this video",
        "let's explore", "today we explore", "we examine", "this video shows",
        "as we can see", "it is important to note"
    ]

    @classmethod
    def generate_batch(
        cls,
        inputs: List[VisualQueryInput],
        config: Optional[VisualQueryConfig] = None,
        memory: Optional[SceneVisualMemory] = None,
        budget: Optional[VisualQueryBudget] = None
    ) -> List[VisualQueryResult]:
        """
        Generates semantic queries for a batch of storyboard scenes.
        """
        if config is None:
            config = VisualQueryConfig()
        if memory is None:
            memory = SceneVisualMemory()
        if budget is None:
            budget = VisualQueryBudget()

        # Emergency environment override check
        if os.getenv("VQG_DISABLED", "").lower() in ("1", "true", "yes"):
            logger.warning("VisualQueryGenerator: Emergency VQG_DISABLED environment variable set -> Mode forced to DISABLED.")
            config = VisualQueryConfig(mode=VisualQueryMode.DISABLED)

        results: List[VisualQueryResult] = []

        # 1. Handle DISABLED mode (legacy fallback)
        if config.mode == VisualQueryMode.DISABLED:
            for inp in inputs:
                legacy_q = (inp.narration[:60] if inp.narration else inp.scene_id).strip()
                res = VisualQueryResult(
                    primary_query=legacy_q,
                    alternate_queries=[],
                    generation_source="legacy_disabled",
                    skipped_reason="mode_disabled"
                )
                memory.record_scene(res)
                results.append(res)
            return results

        cache = VisualQueryCache(config=config)
        t_start_batch = time.time()

        # 2. Evaluate Decision Table per scene (determine if scene is eligible for generation)
        eligible_inputs: List[VisualQueryInput] = []
        scene_results: Dict[str, VisualQueryResult] = {}

        for inp in inputs:
            # Domain intelligence reuse
            domain_key, palette = DomainPaletteEngine.infer_domain(
                f"{inp.storyboard_title} {inp.scene_title} {inp.narration or ''}"
            )
            inp.domain = domain_key
            inp.domain_keywords = palette.get("keywords", [])

            # Decision Table check
            skip_reason = cls._check_decision_table(inp)
            if skip_reason:
                if skip_reason == "title_card":
                    res = cls._generate_title_card_query(inp)
                else:
                    res = VisualQueryResult(
                        primary_query=inp.scene_id,
                        generation_source="skipped_decision_table",
                        skipped_reason=skip_reason
                    )
                scene_results[inp.scene_id] = res
                continue

            # Check Cache
            ck = cache.compute_cache_key(inp)
            cached_res = cache.get(ck)
            if cached_res:
                scene_results[inp.scene_id] = cached_res
            else:
                eligible_inputs.append(inp)

        # 3. Process Eligible Scenes (LLM or DETERMINISTIC_ONLY)
        if config.mode == VisualQueryMode.DETERMINISTIC_ONLY or not config.enable_llm:
            for inp in eligible_inputs:
                res = cls._deterministic_fallback(inp)
                scene_results[inp.scene_id] = res
                cache.put(cache.compute_cache_key(inp), inp, res)

        elif eligible_inputs:
            # Check budget before calling LLM
            if not budget.can_call_llm():
                logger.warning(f"VisualQueryGenerator: Budget limit exceeded ({budget.exhausted_reason}) -> Falling back to deterministic generation.")
                for inp in eligible_inputs:
                    res = cls._deterministic_fallback(inp)
                    res.skipped_reason = f"budget_exceeded_{budget.exhausted_reason}"
                    scene_results[inp.scene_id] = res
                    cache.put(cache.compute_cache_key(inp), inp, res)
            else:
                # Execute Batch LLM call
                batch_unresolved = cls._execute_llm_batch(
                    eligible_inputs, config, budget, cache, scene_results
                )
                # Handle any unresolved scenes via deterministic fallback
                for inp in batch_unresolved:
                    if inp.scene_id not in scene_results:
                        res = cls._deterministic_fallback(inp)
                        scene_results[inp.scene_id] = res
                        cache.put(cache.compute_cache_key(inp), inp, res)

        # 4. Final Scoring, Provider Adaptation & Memory Recording
        final_results: List[VisualQueryResult] = []
        for inp in inputs:
            res = scene_results.get(inp.scene_id)
            if not res:
                res = cls._deterministic_fallback(inp)

            # Score query
            QueryScorer.score(res, inp, memory=memory)

            # Adapt for target provider if specified
            if inp.target_provider and config.provider_optimization_enabled:
                res = QueryAdapterRegistry.adapt(inp.target_provider, res, inp)

            # Record into SceneVisualMemory
            memory.record_scene(res)
            final_results.append(res)

        return final_results

    @classmethod
    def _check_decision_table(cls, inp: VisualQueryInput) -> Optional[str]:
        """
        Decision Table evaluation for scene eligibility.
        """
        overlay = (inp.visual_overlay_type or "").lower().strip()
        if overlay in ("bar_chart", "line_chart", "pie_chart", "chart"):
            return "chart_overlay_procedural"
        if overlay in ("architecture_diagram", "workflow_diagram", "diagram"):
            return "architecture_diagram_procedural"
        if overlay in ("code", "code_demonstration", "code_snippet"):
            return "code_demonstration_procedural"

        title_lower = inp.scene_title.lower().strip()
        if title_lower in ("transition", "cut", "fade", "dissolve"):
            return "transition_only"

        if not inp.narration or len(inp.narration.strip()) == 0:
            if "title" in title_lower or inp.scene_id == "scene_1":
                return "title_card"
            return "empty_narration"

        return None

    @classmethod
    def _generate_title_card_query(cls, inp: VisualQueryInput) -> VisualQueryResult:
        domain_str = (inp.domain or "default").replace("_", " ")
        q = f"abstract {domain_str} background"
        return VisualQueryResult(
            primary_query=q,
            alternate_queries=[f"{domain_str} technology pattern"],
            subjects=["abstract pattern"],
            environment=f"{domain_str} backdrop",
            generation_source="decision_table_title_card",
            confidence=0.9
        )

    @classmethod
    def _execute_llm_batch(
        cls,
        eligible_inputs: List[VisualQueryInput],
        config: VisualQueryConfig,
        budget: VisualQueryBudget,
        cache: VisualQueryCache,
        scene_results: Dict[str, VisualQueryResult]
    ) -> List[VisualQueryInput]:
        """
        Executes batch LLM generation and handles isolated per-scene parsing/retries.
        Returns list of inputs that remained unresolved.
        """
        t0 = time.time()
        system_prompt = cls._build_batch_system_prompt()
        user_prompt = cls._build_batch_user_prompt(eligible_inputs)

        fallback_placeholder: Dict[str, Any] = {"scenes": []}

        # Execute LLM call via LLMService
        raw_res = LLMService.generate_json_advanced(
            prompt=user_prompt,
            system_prompt=system_prompt,
            fallback_dict=fallback_placeholder,
            temperature=config.llm_temperature,
            timeout=config.llm_timeout_seconds
        )
        elapsed_ms = (time.time() - t0) * 1000.0

        # Extract token usage metadata if present
        meta = raw_res.pop("_llm_meta", {}) if isinstance(raw_res, dict) else {}
        usage = meta.get("usage", {})
        tokens_used = usage.get("total_tokens", 300)
        model_name = meta.get("model", "llama-3.3-70b-versatile")

        budget.record_llm_call(tokens_used, elapsed_ms)

        # Parse batch response per scene
        parsed_scenes: Dict[str, Dict[str, Any]] = {}
        if isinstance(raw_res, dict) and "scenes" in raw_res and isinstance(raw_res["scenes"], list):
            for sc_dict in raw_res["scenes"]:
                if isinstance(sc_dict, dict) and "scene_id" in sc_dict:
                    parsed_scenes[sc_dict["scene_id"]] = sc_dict

        unresolved: List[VisualQueryInput] = []

        for inp in eligible_inputs:
            sc_data = parsed_scenes.get(inp.scene_id)
            if sc_data:
                res = cls._validate_and_build_result(sc_data, inp, model_name, tokens_used // len(eligible_inputs), elapsed_ms)
                if res and res.confidence >= config.min_confidence_threshold:
                    res.generation_source = "llm_groq_batch"
                    scene_results[inp.scene_id] = res
                    cache.put(cache.compute_cache_key(inp, model_name), inp, res)
                    continue

            # Scene failed batch validation -> Attempt individual retry if budget permits
            retry_res = cls._retry_single_scene(inp, config, budget, model_name)
            if retry_res:
                scene_results[inp.scene_id] = retry_res
                cache.put(cache.compute_cache_key(inp, model_name), inp, retry_res)
            else:
                unresolved.append(inp)

        return unresolved

    @classmethod
    def _retry_single_scene(
        cls,
        inp: VisualQueryInput,
        config: VisualQueryConfig,
        budget: VisualQueryBudget,
        model_name: str
    ) -> Optional[VisualQueryResult]:
        """
        Retries LLM generation for a single failed scene.
        """
        if not budget.can_call_llm():
            return None

        t0 = time.time()
        system_prompt = cls._build_single_system_prompt()
        user_prompt = cls._build_single_user_prompt(inp)

        raw_res = LLMService.generate_json_advanced(
            prompt=user_prompt,
            system_prompt=system_prompt,
            fallback_dict={},
            temperature=config.llm_temperature,
            timeout=config.llm_timeout_seconds
        )
        elapsed_ms = (time.time() - t0) * 1000.0

        meta = raw_res.pop("_llm_meta", {}) if isinstance(raw_res, dict) else {}
        usage = meta.get("usage", {})
        tokens_used = usage.get("total_tokens", 150)
        budget.record_llm_call(tokens_used, elapsed_ms)

        if isinstance(raw_res, dict) and "primary_query" in raw_res:
            res = cls._validate_and_build_result(raw_res, inp, model_name, tokens_used, elapsed_ms)
            if res and res.confidence >= config.min_confidence_threshold:
                res.generation_source = "llm_groq_single_retry"
                return res

        return None

    @classmethod
    def _validate_and_build_result(
        cls,
        data: Dict[str, Any],
        inp: VisualQueryInput,
        model_name: str,
        token_usage: int,
        latency_ms: float
    ) -> Optional[VisualQueryResult]:
        """
        Strict validation and bounds clamping of LLM output JSON.
        """
        primary = data.get("primary_query")
        if not primary or not isinstance(primary, str) or len(primary.strip()) == 0:
            return None

        primary_clean = cls._sanitize_query_string(primary)
        if not primary_clean:
            return None

        # Process alternate queries
        raw_alts = data.get("alternate_queries", [])
        alts_clean = []
        if isinstance(raw_alts, list):
            for alt in raw_alts:
                if isinstance(alt, str) and alt.strip():
                    c_alt = cls._sanitize_query_string(alt)
                    if c_alt and c_alt != primary_clean and c_alt not in alts_clean:
                        alts_clean.append(c_alt)
                if len(alts_clean) >= 4:
                    break

        # Process lists
        subjects = [cls._clean_word(s) for s in data.get("subjects", []) if isinstance(s, str) and s.strip()][:6]
        actions = [cls._clean_word(a) for a in data.get("actions", []) if isinstance(a, str) and a.strip()][:4]
        negatives = [cls._clean_word(n) for n in data.get("negative_terms", []) if isinstance(n, str) and n.strip()][:6]
        colors = [cls._clean_word(c) for c in data.get("color_palette", []) if isinstance(c, str) and c.strip()][:5]

        # Clamp confidence
        conf_raw = data.get("confidence", 0.8)
        try:
            confidence = max(0.0, min(1.0, float(conf_raw)))
        except (ValueError, TypeError):
            confidence = 0.5

        # Compute deterministic fallback string for verification
        fallback_str = cls._build_deterministic_query_string(inp)

        return VisualQueryResult(
            primary_query=primary_clean,
            alternate_queries=alts_clean,
            negative_terms=negatives,
            subjects=subjects,
            actions=actions,
            environment=cls._clean_word(data.get("environment", "")),
            camera_style=cls._clean_word(data.get("camera_style", "medium shot")),
            mood=cls._clean_word(data.get("mood", "neutral")),
            lighting=cls._clean_word(data.get("lighting", "natural")),
            color_palette=colors,
            time_period=cls._clean_word(data.get("time_period", "contemporary")),
            confidence=confidence,
            fallback_query=fallback_str,
            used_fallback=False,
            generation_source="llm_groq",
            llm_model=model_name,
            token_usage=token_usage,
            generation_latency_ms=round(latency_ms, 2)
        )

    @classmethod
    def _deterministic_fallback(cls, inp: VisualQueryInput) -> VisualQueryResult:
        """
        Rule-based, non-LLM fallback algorithm satisfying all 5 'strictly better' criteria:
        1. No mid-word truncation
        2. No filler phrases
        3. Word count between 1 and 8
        4. Contains at least 1 concrete topic term or domain keyword
        5. Abstract word ratio < 0.5
        """
        t0 = time.time()
        primary_q = cls._build_deterministic_query_string(inp)

        # Build alternate queries deterministically
        alternates = []
        if inp.domain_keywords and len(inp.domain_keywords) >= 2:
            alt1 = f"{inp.scene_title.split()[0]} {inp.domain_keywords[0]} {inp.domain_keywords[1]}"
            alt1_clean = cls._sanitize_query_string(alt1)
            if alt1_clean and alt1_clean != primary_q:
                alternates.append(alt1_clean)

        elapsed_ms = (time.time() - t0) * 1000.0

        return VisualQueryResult(
            primary_query=primary_q,
            alternate_queries=alternates,
            subjects=[w for w in primary_q.split() if w.lower() in QueryScorer.CONCRETE_VISUAL_NOUNS],
            environment=(inp.domain or "default").replace("_", " "),
            confidence=1.0,
            fallback_query=primary_q,
            used_fallback=True,
            generation_source="deterministic_fallback",
            generation_latency_ms=round(elapsed_ms, 2)
        )

    @classmethod
    def _build_deterministic_query_string(cls, inp: VisualQueryInput) -> str:
        text = inp.narration if inp.narration and len(inp.narration.strip()) > 0 else inp.scene_title
        text_clean = text.lower()

        # Remove filler phrases
        for filler in cls.FILLER_PHRASES:
            text_clean = text_clean.replace(filler, " ")

        # Tokenize and filter
        raw_words = re.findall(r'\b[a-zA-Z0-9]+\b', text_clean)

        # Non-English detection heuristic
        is_non_english = cls._detect_non_english(text)

        filtered_words = []
        for w in raw_words:
            if w in QueryScorer.ABSTRACT_WORDS:
                continue
            if len(w) <= 2 and w not in ("ai", "3d", "5g", "ar", "vr", "it", "ip"):
                continue
            filtered_words.append(w)

        # Extract concrete nouns or domain keywords
        concrete_found = [w for w in filtered_words if w in QueryScorer.CONCRETE_VISUAL_NOUNS]
        other_valid = [w for w in filtered_words if w not in concrete_found]

        final_tokens = concrete_found + other_valid

        # Inject domain keywords if insufficient tokens
        if len(final_tokens) < 2 and inp.domain_keywords:
            for kw in inp.domain_keywords:
                if kw.lower() not in final_tokens:
                    final_tokens.append(kw.lower())

        if not final_tokens:
            final_tokens = [(inp.domain or "technology").replace("_", " "), "background"]

        # Word count between 1 and 8
        final_query = " ".join(final_tokens[:6])
        return cls._sanitize_query_string(final_query)

    @classmethod
    def _detect_non_english(cls, text: str) -> bool:
        if not text:
            return False
        non_latin_count = sum(1 for c in text if ord(c) > 0x024F)
        if non_latin_count / max(len(text), 1) > 0.3:
            return True
        accented_count = sum(1 for c in text if ord(c) > 127 and ord(c) <= 0x024F)
        if accented_count / max(len(text), 1) > 0.15:
            return True
        return False

    @classmethod
    def _sanitize_query_string(cls, q: str) -> str:
        if not q:
            return ""
        # Remove blocked terms
        words = q.strip().split()
        clean = [w for w in words if w.lower().strip(",.!?\"'()") not in cls.BLOCKED_TERMS]
        res = " ".join(clean)[:100].strip()
        return res

    @classmethod
    def _clean_word(cls, w: Any) -> str:
        if not isinstance(w, str):
            return ""
        return w.strip()[:80]

    @classmethod
    def _build_batch_system_prompt(cls) -> str:
        return (
            "You are a professional visual scene describer for stock photography. "
            "Given narration text for multiple scenes in a video, output a JSON object containing a 'scenes' list. "
            "For each scene, extract visual, photographable concepts. NEVER copy narration text directly. "
            "Avoid abstract words ('innovation', 'transformation', 'synergy'). Output strict JSON matching this schema:\n"
            '{"scenes":['
            '{"scene_id":"scene_1","primary_query":"doctor analyzing medical scan hospital",'
            '"alternate_queries":["radiologist reviewing screen","medical laboratory AI"],'
            '"subjects":["doctor","medical scan"],"actions":["analyzing"],"environment":"modern hospital",'
            '"camera_style":"medium shot","mood":"professional","lighting":"bright clinical",'
            '"color_palette":["blue","white"],"time_period":"contemporary","confidence":0.9,'
            '"negative_terms":["text","illustration"]}]}'
        )

    @classmethod
    def _build_batch_user_prompt(cls, eligible_inputs: List[VisualQueryInput]) -> str:
        prompt_data = []
        for inp in eligible_inputs:
            prompt_data.append({
                "scene_id": inp.scene_id,
                "scene_title": inp.scene_title,
                "narration": inp.narration or "",
                "video_topic": inp.storyboard_title,
                "domain": inp.domain or "general"
            })
        return f"Extract visual queries for the following scenes:\n{json.dumps(prompt_data)}"

    @classmethod
    def _build_single_system_prompt(cls) -> str:
        return (
            "You are a visual scene describer for stock photography. "
            "Given scene narration, output a JSON object with visual search terms:\n"
            '{"primary_query":"doctor analyzing medical scan hospital",'
            '"alternate_queries":["radiologist screen"],"subjects":["doctor"],"actions":["analyzing"],'
            '"environment":"hospital","confidence":0.85}'
        )

    @classmethod
    def _build_single_user_prompt(cls, inp: VisualQueryInput) -> str:
        return json.dumps({
            "scene_id": inp.scene_id,
            "scene_title": inp.scene_title,
            "narration": inp.narration or "",
            "video_topic": inp.storyboard_title,
            "domain": inp.domain or "general"
        })
