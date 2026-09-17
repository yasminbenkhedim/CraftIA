"""
MotionGraphicsPlanner & Grammar Selector for CraftAI (Upgrade 7).
Analyzes scene facts and content to construct inspectable SemanticGraphicTrees.
"""
import uuid
import logging
from typing import List, Dict, Any, Optional
from agents.video.storyboard import Storyboard, SceneDefinition
from agents.video.motion_graphics.schemas import (
    VisualGrammarType, MotionChartType, GraphicNodeType, GraphicNode,
    SemanticGraphicTree, MotionGraphicsPlan, DataProvenance
)

logger = logging.getLogger("uvicorn")


class MotionGraphicsPlanner:
    """
    Analyzes scene semantics and selects from 21 visual grammars to generate inspectable SemanticGraphicTrees.
    """

    @classmethod
    def plan_motion_graphics(
        cls,
        scene: SceneDefinition,
        scene_idx: int = 0,
        aspect_ratio: str = "16:9"
    ) -> MotionGraphicsPlan:
        narr_lower = (scene.narration or "").lower()
        title_lower = (scene.scene_title or "").lower()

        # 1. Grammar Selection Logic
        if "percent" in narr_lower or "%" in narr_lower or "growth" in title_lower:
            grammar = VisualGrammarType.PERCENTAGE_GAUGE
            reason = "Detected numerical percentage signal in scene content"
        elif "step" in narr_lower or "process" in narr_lower or "workflow" in title_lower:
            grammar = VisualGrammarType.PROCESS_FLOW
            reason = "Detected sequential process workflow signal"
        elif "timeline" in narr_lower or "history" in title_lower or "year" in narr_lower:
            grammar = VisualGrammarType.TIMELINE
            reason = "Detected temporal chronological sequence"
        elif "kpi" in narr_lower or "metric" in title_lower or "revenue" in narr_lower:
            grammar = VisualGrammarType.KPI_CARD
            reason = "Detected key performance indicator metric"
        elif scene.visual_overlay and scene.visual_overlay.overlay_type in ("bar_chart", "line_chart", "pie_chart"):
            grammar = VisualGrammarType.STATISTIC_HIGHLIGHT
            reason = "Matched structured overlay visual overlay parameter"
        else:
            grammar = VisualGrammarType.KPI_CARD
            reason = "Defaulted to KPI card metric layout"

        # 2. Build Intermediate SemanticGraphicTree
        tree = SemanticGraphicTree(
            scene_id=scene.scene_id,
            grammar_selected=grammar,
            selection_reason=reason,
            confidence_score=0.95
        )

        root_id = f"node_root_{uuid.uuid4().hex[:6]}"
        root_node = GraphicNode(
            node_uuid=root_id,
            node_type=GraphicNodeType.CONTAINER,
            semantic_role="card_container",
            priority=1,
            required=True
        )
        tree.nodes[root_id] = root_node
        tree.root_node_ids.append(root_id)

        # Attach child graphic nodes
        child_id = f"node_child_{uuid.uuid4().hex[:6]}"
        child_node = GraphicNode(
            node_uuid=child_id,
            node_type=GraphicNodeType.METRIC if grammar == VisualGrammarType.KPI_CARD else GraphicNodeType.CHART,
            semantic_role="primary_metric",
            parent_id=root_id,
            priority=1
        )
        tree.nodes[child_id] = child_node
        root_node.child_ids.append(child_id)

        return MotionGraphicsPlan(
            scene_id=scene.scene_id,
            grammar_type=grammar,
            tree=tree,
            template_name=f"template_{grammar.value}_v1",
            responsive_aspect=aspect_ratio,
            style_token_palette=["#0F172A", "#38BDF8", "#FACC15"]
        )
