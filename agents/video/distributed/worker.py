"""
Distributed Worker Capabilities & Descriptors for VideoAgent (Phase 8).
Defines CPUWorker, GPUWorker, RenderWorker descriptors and hardware capabilities.
"""
import time
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field


class WorkerStatus(str, Enum):
    HEALTHY = "HEALTHY"
    BUSY = "BUSY"
    DRAINING = "DRAINING"
    OFFLINE = "OFFLINE"
    LOST = "LOST"


class WorkerCapability(BaseModel):
    cpu_cores: int = 8
    memory_gb: float = 16.0
    has_gpu: bool = False
    gpu_model: Optional[str] = None
    gpu_memory_gb: float = 0.0
    supported_codecs: List[str] = Field(default_factory=lambda: ["libx264", "libvpx-vp9"])
    supported_stages: List[str] = Field(default_factory=lambda: ["planning", "rendering", "export"])


class WorkerDescriptor(BaseModel):
    worker_id: str
    worker_type: str = "RenderWorker"
    capability: WorkerCapability = Field(default_factory=WorkerCapability)
    status: WorkerStatus = WorkerStatus.HEALTHY
    last_heartbeat_timestamp: float = Field(default_factory=time.time)
    current_workload_count: int = 0


class CPUWorker(WorkerDescriptor):
    worker_type: str = "CPUWorker"


class GPUWorker(WorkerDescriptor):
    worker_type: str = "GPUWorker"
    capability: WorkerCapability = Field(default_factory=lambda: WorkerCapability(has_gpu=True, gpu_model="NVIDIA RTX 4090", gpu_memory_gb=24.0))


class RenderWorker(WorkerDescriptor):
    worker_type: str = "RenderWorker"
