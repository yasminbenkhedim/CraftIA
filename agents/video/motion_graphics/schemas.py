"""
Typed Schemas & Intermediate Representations for Motion Graphics Engine (Upgrade 7).
Includes 21 Visual Grammars, 15 Chart Types, Typed Datum Schemas, SemanticGraphicTree, and Diagnostics.
"""
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple, Union
from pydantic import BaseModel, Field


# ============================================================================
# VISUAL GRAMMARS & CHART TYPES
# ============================================================================

class VisualGrammarType(str, Enum):
    KPI_CARD = "kpi_card"
    ANIMATED_COUNTER = "animated_counter"
    PERCENTAGE_GAUGE = "percentage_gauge"
    PROGRESS_BAR = "progress_bar"
    COMPARISON_CARD = "comparison_card"
    RANKED_LIST = "ranked_list"
    ICON_GRID = "icon_grid"
    PROCESS_FLOW = "process_flow"
    STEP_BY_STEP = "step_by_step"
    TIMELINE = "timeline"
    ROADMAP = "roadmap"
    FUNNEL = "funnel"
    HIERARCHY_TREE = "hierarchy_tree"
    RELATIONSHIP_GRAPH = "relationship_graph"
    BEFORE_AFTER = "before_after"
    MAP_CALLOUT = "map_callout"
    QUOTE_CARD = "quote_card"
    STATISTIC_HIGHLIGHT = "statistic_highlight"
    FEATURE_MATRIX = "feature_matrix"
    ANNOTATED_IMAGE = "annotated_image"
    DATA_STORY = "data_story"


class MotionChartType(str, Enum):
    BAR = "bar"
    GROUPED_BAR = "grouped_bar"
    STACKED_BAR = "stacked_bar"
    LINE = "line"
    AREA = "area"
    PIE = "pie"
    DONUT = "donut"
    SCATTER = "scatter"
    BUBBLE = "bubble"
    RADAR = "radar"
    WATERFALL = "waterfall"
    FUNNEL_CHART = "funnel_chart"
    GAUGE = "gauge"
    HEATMAP = "heatmap"
    SPARKLINE = "sparkline"


class GraphicNodeType(str, Enum):
    CONTAINER = "container"
    METRIC = "metric"
    CHART = "chart"
    TEXT = "text"
    ICON = "icon"
    CONNECTOR = "connector"
    ANNOTATION = "annotation"
    MEDIA_REF = "media_ref"
    PROCESS = "process"
    TIMELINE = "timeline"
    HIERARCHY = "hierarchy"
    RELATIONSHIP = "relationship"


# ============================================================================
# TYPED DATA MODELS WITH PROVENANCE
# ============================================================================

class DataProvenance(BaseModel):
    source_id: str = "storyboard"
    source_field: str = "narration"
    source_value: Any = None
    transformation: str = "identity"
    display_value: str = ""
    unit: Optional[str] = None
    confidence: float = 1.0
    validation_status: str = "valid"


class MetricDatum(BaseModel):
    label: str
    value: float
    unit: Optional[str] = None
    target_value: Optional[float] = None
    change_percent: Optional[float] = None
    provenance: DataProvenance = Field(default_factory=DataProvenance)


class CategoryDatum(BaseModel):
    category: str
    value: float
    color_hex: Optional[str] = None
    provenance: DataProvenance = Field(default_factory=DataProvenance)


class TimeSeriesDatum(BaseModel):
    timestamp_str: str
    value: float
    provenance: DataProvenance = Field(default_factory=DataProvenance)


class ProcessStep(BaseModel):
    step_number: int
    title: str
    description: Optional[str] = None
    icon_name: Optional[str] = None
    provenance: DataProvenance = Field(default_factory=DataProvenance)


# ============================================================================
# SEMANTIC GRAPHIC TREE SCHEMAS
# ============================================================================

class GraphicNode(BaseModel):
    node_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    node_type: GraphicNodeType = GraphicNodeType.CONTAINER
    semantic_role: str = "card_container"
    priority: int = 1
    required: bool = True
    parent_id: Optional[str] = None
    child_ids: List[str] = Field(default_factory=list)
    provenance: DataProvenance = Field(default_factory=DataProvenance)
    layout_constraints: Dict[str, Any] = Field(default_factory=dict)
    style_bindings: Dict[str, Any] = Field(default_factory=dict)
    animation_intent: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class SemanticGraphicTree(BaseModel):
    tree_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scene_id: str
    root_node_ids: List[str] = Field(default_factory=list)
    nodes: Dict[str, GraphicNode] = Field(default_factory=dict)
    grammar_selected: VisualGrammarType = VisualGrammarType.KPI_CARD
    selection_reason: str = "Selected based on metric density"
    confidence_score: float = 0.95


class MotionGraphicsPlan(BaseModel):
    plan_uuid: str = Field(default_factory=lambda: str(uuid.uuid4()))
    scene_id: str
    grammar_type: VisualGrammarType
    tree: SemanticGraphicTree
    template_name: str = "standard_kpi_v1"
    responsive_aspect: str = "16:9"
    style_token_palette: List[str] = Field(default_factory=lambda: ["#0F172A", "#38BDF8"])
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# DIAGNOSTICS & STATISTICS
# ============================================================================

class MotionGraphicsStatistics(BaseModel):
    semantic_node_count: int = 0
    compiled_layer_count: int = 0
    animation_track_count: int = 0
    chart_count: int = 0
    icon_count: int = 0
    connector_count: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    template_reuse_rate: float = 0.90
    planning_time_ms: float = 12.5
    layout_time_ms: float = 15.0
    compile_time_ms: float = 18.0
    compositing_overhead_percent: float = 4.5


class MotionGraphicsDiagnosticReport(BaseModel):
    video_id: str
    grammar_score: float = 0.92
    grammar_selection_reason: str = "Matched metric content"
    data_validity_score: float = 0.98
    chart_integrity_score: float = 0.95
    layout_score: float = 0.90
    animation_score: float = 0.92
    readability_score: float = 0.95
    accessibility_score: float = 0.94
    style_consistency_score: float = 0.96
    camera_safety_score: float = 0.95
    information_density_score: float = 0.85
    warnings: List[str] = Field(default_factory=list)
    stats: MotionGraphicsStatistics = Field(default_factory=MotionGraphicsStatistics)
