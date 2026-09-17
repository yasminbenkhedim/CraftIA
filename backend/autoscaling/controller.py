"""
Multi-Signal Worker Autoscaling Controller for CraftAI (Upgrade 11).

Evaluates target worker replicas using multiple metrics:
- CPU utilization (Target 70%)
- GPU utilization (Target 80%)
- Celery Queue length / depth (Target max 5 pending tasks per worker)
- Scheduled Cron scaling (Time-of-day / Peak hours boost)

Safety features:
- Separate Scale-Up (60s) and Scale-Down (300s) Cooldown timers to prevent flapping
- Burst Scale Protection (caps single scale step to max 3x current replica count)
- Minimum (1) and Maximum (20) replica bounds
"""
import time
import math
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger("uvicorn")


class AutoscalingController:
    """Production Multi-Signal Autoscaling Controller."""

    MIN_REPLICAS = 1
    MAX_REPLICAS = 20

    TARGET_CPU_UTILIZATION = 0.70    # 70%
    TARGET_GPU_UTILIZATION = 0.80    # 80%
    TASKS_PER_WORKER = 5.0           # Max 5 pending tasks per worker

    SCALE_UP_COOLDOWN_SEC = 60       # 1 minute
    SCALE_DOWN_COOLDOWN_SEC = 300    # 5 minutes
    MAX_BURST_MULTIPLIER = 3.0       # Max 3x expansion per step

    def __init__(self):
        self.last_scale_time = 0.0
        self.last_scale_direction = "NONE"
        self.current_replicas = 3

    def evaluate_scaling_decision(
        self,
        current_replicas: int,
        metrics: Dict[str, Any],
        scheduled_min_replicas: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Evaluate all scaling signals and compute recommended target replica count.
        """
        now = time.time()
        self.current_replicas = current_replicas

        # Extract metric signals
        cpu_util = float(metrics.get("cpu_utilization", 0.50))
        gpu_util = float(metrics.get("gpu_utilization", 0.50))
        queue_depth = int(metrics.get("total_queue_depth", 0))

        # Signal 1: CPU-based target
        cpu_target = math.ceil(current_replicas * (cpu_util / max(self.TARGET_CPU_UTILIZATION, 0.1)))

        # Signal 2: GPU-based target
        gpu_target = math.ceil(current_replicas * (gpu_util / max(self.TARGET_GPU_UTILIZATION, 0.1)))

        # Signal 3: Queue-length target
        queue_target = math.ceil(queue_depth / self.TASKS_PER_WORKER)

        # Signal 4: Scheduled Cron min replicas
        schedule_target = scheduled_min_replicas or self.MIN_REPLICAS

        # Combine signals — maximum required replicas across all demand metrics
        desired_replicas = max(cpu_target, gpu_target, queue_target, schedule_target, self.MIN_REPLICAS)
        desired_replicas = min(desired_replicas, self.MAX_REPLICAS)

        # Apply Cooldown checks
        time_since_last_scale = now - self.last_scale_time

        action = "HOLD"
        final_target = current_replicas
        reason = "Metrics within target bounds"

        if desired_replicas > current_replicas:
            # Scale UP attempt
            if time_since_last_scale < self.SCALE_UP_COOLDOWN_SEC:
                reason = f"Scale up suppressed by cooldown ({int(self.SCALE_UP_COOLDOWN_SEC - time_since_last_scale)}s remaining)"
            else:
                # Burst protection: cap to 3x current
                max_allowed_step = math.ceil(current_replicas * self.MAX_BURST_MULTIPLIER)
                final_target = min(desired_replicas, max_allowed_step)
                action = "SCALE_UP"
                reason = f"High demand detected (CPU: {cpu_util*100:.1f}%, GPU: {gpu_util*100:.1f}%, Queue: {queue_depth})"
                self.last_scale_time = now
                self.last_scale_direction = "UP"

        elif desired_replicas < current_replicas:
            # Scale DOWN attempt
            if time_since_last_scale < self.SCALE_DOWN_COOLDOWN_SEC:
                reason = f"Scale down suppressed by cooldown ({int(self.SCALE_DOWN_COOLDOWN_SEC - time_since_last_scale)}s remaining)"
            else:
                final_target = max(desired_replicas, self.MIN_REPLICAS)
                action = "SCALE_DOWN"
                reason = f"Low demand detected (CPU: {cpu_util*100:.1f}%, GPU: {gpu_util*100:.1f}%, Queue: {queue_depth})"
                self.last_scale_time = now
                self.last_scale_direction = "DOWN"

        self._record_telemetry(current_replicas, final_target, action)

        return {
            "current_replicas": current_replicas,
            "recommended_replicas": final_target,
            "action": action,
            "reason": reason,
            "signals": {
                "cpu_target": cpu_target,
                "gpu_target": gpu_target,
                "queue_target": queue_target,
                "schedule_target": schedule_target
            },
            "timestamp": now
        }

    def _record_telemetry(self, current: int, target: int, action: str):
        try:
            from backend.observability.metrics import metrics
            metrics.set_gauge("worker_autoscale_current_replicas", current)
            metrics.set_gauge("worker_autoscale_target_replicas", target)
            if action != "HOLD":
                metrics.inc_counter(f"worker_autoscale_{action.lower()}_total", 1)
        except Exception:
            pass


autoscaling_controller = AutoscalingController()
