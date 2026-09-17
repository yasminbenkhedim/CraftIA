"""
StatelessWorker & WorkerRegistry for CraftAI (Upgrade 10).
Defines worker lifecycle management, heartbeat monitoring, and stateless task execution.
"""
import uuid
import time
import logging
from enum import Enum
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger("uvicorn")


class WorkerLifecycleState(str, Enum):
    STARTING = "STARTING"
    READY = "READY"
    BUSY = "BUSY"
    DRAINING = "DRAINING"
    UNHEALTHY = "UNHEALTHY"
    OFFLINE = "OFFLINE"


class WorkerRecord(BaseModel):
    worker_id: str = Field(default_factory=lambda: f"wrk_{uuid.uuid4().hex[:8]}")
    worker_role: str                 # "planning", "rendering", "critic"
    state: WorkerLifecycleState = WorkerLifecycleState.READY
    gpu_count: int = 1
    started_at: float = Field(default_factory=time.time)
    last_heartbeat: float = Field(default_factory=time.time)


class WorkerRegistry:
    """
    Tracks registered stateless workers, heartbeats, and lifecycle states.
    """

    def __init__(self, heartbeat_timeout_sec: float = 15.0):
        self.heartbeat_timeout_sec = heartbeat_timeout_sec
        self.workers: Dict[str, WorkerRecord] = {}

    def register_worker(self, role: str, gpu_count: int = 1) -> WorkerRecord:
        wrk = WorkerRecord(worker_role=role, gpu_count=gpu_count)
        self.workers[wrk.worker_id] = wrk
        return wrk

    def heartbeat(self, worker_id: str) -> bool:
        if worker_id in self.workers:
            self.workers[worker_id].last_heartbeat = time.time()
            if self.workers[worker_id].state == WorkerLifecycleState.UNHEALTHY:
                self.workers[worker_id].state = WorkerLifecycleState.READY
            return True
        return False

    def check_health(self):
        now = time.time()
        for wrk in self.workers.values():
            if now - wrk.last_heartbeat > self.heartbeat_timeout_sec:
                wrk.state = WorkerLifecycleState.UNHEALTHY
