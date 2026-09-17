"""
Worker Registry & Capability Matcher for VideoAgent (Phase 8).
Coordinates worker registration, heartbeats, health probes, draining, and capability matching.
"""
import time
import logging
from typing import Dict, Any, List, Optional
from agents.video.distributed.worker import WorkerDescriptor, WorkerStatus, WorkerCapability

logger = logging.getLogger("uvicorn")


class WorkerRegistry:
    """
    Worker Registry.
    Tracks active worker nodes and prevents scheduling GPU-requiring tasks onto CPU-only workers.
    """

    _workers: Dict[str, WorkerDescriptor] = {}
    _timeout_threshold_sec: float = 60.0

    @classmethod
    def register_worker(cls, worker: WorkerDescriptor) -> str:
        worker.last_heartbeat_timestamp = time.time()
        worker.status = WorkerStatus.HEALTHY
        cls._workers[worker.worker_id] = worker
        logger.info(f"WorkerRegistry: Registered worker '{worker.worker_id}' (Type: {worker.worker_type}, GPU: {worker.capability.has_gpu})")
        return worker.worker_id

    @classmethod
    def heartbeat(cls, worker_id: str) -> bool:
        worker = cls._workers.get(worker_id)
        if worker and worker.status != WorkerStatus.DRAINING:
            worker.last_heartbeat_timestamp = time.time()
            worker.status = WorkerStatus.HEALTHY
            return True
        return False

    @classmethod
    def find_capable_worker(cls, require_gpu: bool = False, stage_name: Optional[str] = None) -> Optional[WorkerDescriptor]:
        """
        Finds a healthy worker matching hardware and capability requirements.
        Strictly prevents scheduling GPU-only tasks on CPU workers.
        """
        cls.check_health()
        for w in cls._workers.values():
            if w.status != WorkerStatus.HEALTHY:
                continue
            if require_gpu and not w.capability.has_gpu:
                continue
            if stage_name and stage_name not in w.capability.supported_stages:
                continue
            return w
        return None

    @classmethod
    def drain_worker(cls, worker_id: str) -> bool:
        worker = cls._workers.get(worker_id)
        if worker:
            worker.status = WorkerStatus.DRAINING
            logger.info(f"WorkerRegistry: Draining worker '{worker_id}'")
            return True
        return False

    @classmethod
    def check_health(cls) -> List[str]:
        now = time.time()
        lost_ids = []
        for wid, w in cls._workers.items():
            if w.status in [WorkerStatus.HEALTHY, WorkerStatus.BUSY]:
                if now - w.last_heartbeat_timestamp > cls._timeout_threshold_sec:
                    w.status = WorkerStatus.LOST
                    lost_ids.append(wid)
                    logger.warning(f"WorkerRegistry: Worker '{wid}' marked LOST due to heartbeat timeout.")
        return lost_ids

    @classmethod
    def list_workers(cls) -> List[WorkerDescriptor]:
        cls.check_health()
        return list(cls._workers.values())
