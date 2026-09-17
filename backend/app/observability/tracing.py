"""
Observability Tracing Module for VideoAgent (Phase 8).
Provides OpenTelemetry-compatible TraceContext recording trace spans across distributed pipeline stages.
"""
import time
import uuid
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class TraceSpan(BaseModel):
    span_id: str
    trace_id: str
    operation_name: str
    start_time_sec: float
    end_time_sec: Optional[float] = None
    duration_sec: float = 0.0
    tags: Dict[str, str] = Field(default_factory=dict)


class TraceContext:
    """Trace Context Manager."""

    _spans: Dict[str, TraceSpan] = {}

    @classmethod
    def start_span(cls, operation_name: str, trace_id: Optional[str] = None) -> TraceSpan:
        tid = trace_id or str(uuid.uuid4())
        sid = str(uuid.uuid4())[:8]
        span = TraceSpan(span_id=sid, trace_id=tid, operation_name=operation_name, start_time_sec=time.time())
        cls._spans[sid] = span
        return span

    @classmethod
    def end_span(cls, span_id: str):
        span = cls._spans.get(span_id)
        if span:
            span.end_time_sec = time.time()
            span.duration_sec = round(span.end_time_sec - span.start_time_sec, 3)
            logger.info(f"TraceContext: Ended span '{span.operation_name}' ({span.duration_sec}s)")

    @classmethod
    def list_spans(cls) -> List[TraceSpan]:
        return list(cls._spans.values())
