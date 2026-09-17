"""
QueryScorer -- 12-Dimension Quality Evaluator for Visual Queries (Upgrade 2).
Evaluates visual specificity, concrete noun ratio, search friendliness, abstract term penalties,
and visual memory duplicate penalties.
"""
import re
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Set, Optional, Tuple
from agents.video.visual_query_schemas import VisualQueryResult, VisualQueryInput
from agents.video.scene_visual_memory import SceneVisualMemory

logger = logging.getLogger("uvicorn")


@dataclass
class ScorerWeights:
    visual_specificity: float = 0.15
    concrete_noun_ratio: float = 0.12
    action_visibility: float = 0.08
    environment_clarity: float = 0.08
    search_friendliness: float = 0.12
    abstract_penalty: float = 0.10
    query_diversity: float = 0.08
    duplicate_subject_penalty: float = 0.05
    provider_compatibility: float = 0.07
    historical_success: float = 0.05
    scene_topic_relevance: float = 0.05
    confidence_from_llm: float = 0.05

    def validate_and_normalize(self):
        total = (
            self.visual_specificity + self.concrete_noun_ratio + self.action_visibility +
            self.environment_clarity + self.search_friendliness + self.abstract_penalty +
            self.query_diversity + self.duplicate_subject_penalty + self.provider_compatibility +
            self.historical_success + self.scene_topic_relevance + self.confidence_from_llm
        )
        if abs(total - 1.0) > 1e-4:
            logger.warning(f"ScorerWeights sum ({total:.4f}) is not 1.0. Normalizing weights.")
            if total > 0:
                self.visual_specificity /= total
                self.concrete_noun_ratio /= total
                self.action_visibility /= total
                self.environment_clarity /= total
                self.search_friendliness /= total
                self.abstract_penalty /= total
                self.query_diversity /= total
                self.duplicate_subject_penalty /= total
                self.provider_compatibility /= total
                self.historical_success /= total
                self.scene_topic_relevance /= total
                self.confidence_from_llm /= total


class QueryScorer:
    """
    Evaluates visual search queries against 12 quality dimensions.
    """

    ABSTRACT_WORDS: Set[str] = {
        "transformation", "transforming", "transform", "innovation", "innovative",
        "disruption", "disruptive", "paradigm", "synergy", "excellence", "breakthrough",
        "revolution", "revolutionary", "comprehensive", "exceptional", "outstanding",
        "remarkable", "leveraging", "leverage", "utilizing", "utilize", "implementing",
        "implementation", "facilitating", "facilitate", "empowering", "empower",
        "enhancement", "enhancing", "optimization", "optimizing", "strategic", "strategy",
        "solutions", "solution", "system", "systems", "platform", "platforms",
        "world", "worldwide", "global", "modern", "future", "futuristic", "next",
        "generation", "cutting", "edge", "leading", "industry", "business", "market",
        "growth", "value", "impact", "today", "explore", "welcome", "overview"
    }

    CONCRETE_VISUAL_NOUNS: Set[str] = {
        "doctor", "nurse", "patient", "hospital", "clinic", "laboratory", "lab",
        "scientist", "researcher", "microscope", "stethoscope", "scanner", "mri",
        "xray", "computer", "laptop", "screen", "monitor", "software", "code",
        "robot", "robotic", "chip", "processor", "server", "data", "datacenter",
        "building", "skyscraper", "city", "skyline", "street", "traffic", "car",
        "office", "desk", "executive", "meeting", "presentation", "chart", "graph",
        "mountain", "peak", "ocean", "sea", "river", "forest", "tree", "plant",
        "field", "farm", "solar", "wind", "turbine", "factory", "worker", "engineer",
        "helmet", "satellite", "space", "rocket", "planet", "earth", "globe",
        "book", "pen", "paper", "classroom", "student", "teacher", "microchip",
        "healthcare", "health", "medical", "medicine", "intelligence", "ai", "tech",
        "finance", "financial", "market", "markets", "stock", "volatility", "growth",
        "quantum", "computing", "qubit", "energy", "infrastructure", "radiologist", "radiologists",
        "tumor", "tumors", "cybersecurity", "security", "threat", "biodiversity", "conservation",
        "vehicle", "vehicles", "traffic", "car", "city", "benchmark", "benchmarks", "throughput",
        "pipeline", "pipelines", "score", "scores", "data"
    }

    ACTION_VERBS: Set[str] = {
        "analyzing", "analyze", "checking", "check", "examining", "examine",
        "looking", "look", "using", "use", "operating", "operate", "working", "work",
        "typing", "type", "coding", "code", "running", "run", "walking", "walk",
        "standing", "stand", "sitting", "sit", "talking", "talk", "discussing", "discuss",
        "pointing", "point", "holding", "hold", "testing", "test", "measuring", "measure",
        "building", "build", "driving", "drive", "flying", "fly"
    }

    @classmethod
    def score(
        cls,
        vq_result: VisualQueryResult,
        vq_input: VisualQueryInput,
        memory: Optional[SceneVisualMemory] = None,
        weights: Optional[ScorerWeights] = None
    ) -> float:
        """
        Computes composite score for a VisualQueryResult.
        Updates vq_result fields (quality_score, specificity_score, concrete_noun_count) in-place.
        """
        if weights is None:
            weights = ScorerWeights()
        weights.validate_and_normalize()

        query = vq_result.primary_query or ""
        words = [w.lower().strip(",.!?\"'()") for w in query.split() if w.strip()]
        word_count = len(words)

        # 1. Visual Specificity (ratio of concrete terms or subjects to total words)
        concrete_count = sum(1 for w in words if w in cls.CONCRETE_VISUAL_NOUNS)
        vq_result.concrete_noun_count = concrete_count
        specificity = min(1.0, (concrete_count + len(vq_result.subjects)) / max(word_count, 1))
        vq_result.specificity_score = round(specificity, 4)

        # 2. Concrete Noun Ratio
        noun_ratio = min(1.0, concrete_count / max(word_count, 1))

        # 3. Action Visibility
        has_action = 1.0 if any(w in cls.ACTION_VERBS for w in words) or bool(vq_result.actions) else 0.0

        # 4. Environment Clarity
        has_env = 1.0 if vq_result.environment and len(vq_result.environment.strip()) > 0 else 0.0

        # 5. Search Friendliness (3-8 words is optimal)
        if 3 <= word_count <= 8:
            search_friendliness = 1.0
        elif 1 <= word_count < 3:
            search_friendliness = 0.6
        elif 8 < word_count <= 12:
            search_friendliness = 0.7
        else:
            search_friendliness = 0.3

        # 6. Abstract Penalty (1 - abstract_ratio)
        abstract_count = sum(1 for w in words if w in cls.ABSTRACT_WORDS)
        abstract_ratio = abstract_count / max(word_count, 1)
        abstract_score = max(0.0, 1.0 - abstract_ratio)

        # 7 & 8. Memory Penalties (Diversity & Subject repetition)
        if memory:
            dup_q_pen = memory.duplicate_query_penalty(query)
            query_diversity = max(0.0, 1.0 - dup_q_pen)
            dup_sub_pen = memory.duplicate_subject_penalty(vq_result.subjects)
            subject_diversity = max(0.0, 1.0 - dup_sub_pen)
        else:
            query_diversity = 1.0
            subject_diversity = 1.0

        # 9. Provider Compatibility (Check if query avoids known problematic patterns)
        provider = vq_input.target_provider or "openverse_stock"
        if provider == "openverse_stock":
            prov_compat = 1.0 if 2 <= word_count <= 5 else 0.7
        else:
            prov_compat = 1.0 if 3 <= word_count <= 7 else 0.8

        # 10. Historical Success (Placeholder for session telemetry, default 1.0)
        hist_success = 1.0

        # 11. Scene Topic Relevance
        topic_words = set((vq_input.storyboard_title + " " + (vq_input.domain or "")).lower().split())
        topic_overlap = sum(1 for w in words if w in topic_words or w in vq_input.domain_keywords)
        topic_relevance = min(1.0, topic_overlap / max(min(word_count, 3), 1))

        # 12. Confidence from LLM
        confidence = max(0.0, min(1.0, vq_result.confidence))

        # Composite Weighted Sum
        composite = (
            weights.visual_specificity * specificity +
            weights.concrete_noun_ratio * noun_ratio +
            weights.action_visibility * has_action +
            weights.environment_clarity * has_env +
            weights.search_friendliness * search_friendliness +
            weights.abstract_penalty * abstract_score +
            weights.query_diversity * query_diversity +
            weights.duplicate_subject_penalty * subject_diversity +
            weights.provider_compatibility * prov_compat +
            weights.historical_success * hist_success +
            weights.scene_topic_relevance * topic_relevance +
            weights.confidence_from_llm * confidence
        )

        vq_result.quality_score = round(max(0.0, min(1.0, composite)), 4)
        return vq_result.quality_score
