from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class SlideItem(BaseModel):
    slide_title: str
    subtitle: Optional[str] = None
    layout_type: str = "bullet_list"  # title_slide, bullet_list, two_column, three_column, metrics_grid, timeline_steps
    points: List[str] = Field(default_factory=list)
    
    # Layout-specific fields
    left_title: Optional[str] = None
    left_points: Optional[List[str]] = None
    right_title: Optional[str] = None
    right_points: Optional[List[str]] = None
    
    columns: Optional[List[Dict[str, Any]]] = None  # For three_column: [{"title": "...", "points": [...]}]
    metrics: Optional[List[Dict[str, str]]] = None  # For metrics_grid: [{"metric": "...", "label": "..."}]
    steps: Optional[List[Dict[str, str]]] = None    # For timeline_steps: [{"step": "01", "title": "...", "desc": "..."}]
    
    chart_type: Optional[str] = None                # column, bar, line, pie
    chart_data: Optional[Dict[str, Any]] = None      # {"categories": [...], "series": [{"name": "...", "values": [...]}]}
    image_url: Optional[str] = None                 # Local file path or image URL

class PresentationDeckSchema(BaseModel):
    title: str
    subtitle: Optional[str] = None
    theme: str = "corporate_navy"
    slides: List[SlideItem] = Field(default_factory=list)

class ReportSection(BaseModel):
    section_title: str
    content: str
    bullets: List[str] = Field(default_factory=list)

class ReportSchema(BaseModel):
    title: str
    subtitle: Optional[str] = None
    abstract: str
    sections: List[ReportSection] = Field(default_factory=list)

class VideoScriptSchema(BaseModel):
    title: str
    subtitle: Optional[str] = None
    duration_sec: int = 5
    scenes: List[Dict[str, Any]] = Field(default_factory=list)

class DefectItem(BaseModel):
    location: str
    severity: str  # LOW, MEDIUM, CRITICAL
    description: str
    suggested_fix: str

class CritiqueReportSchema(BaseModel):
    is_approved: bool
    quality_score: float  # 0.0 to 1.0
    defects: List[DefectItem] = Field(default_factory=list)
    revision_instructions: Optional[str] = None
