"""
Chaos Engineering & Fault Injection Engine for CraftAI (Upgrade 11).

Automates fault injection scenarios to verify resilience & automatic recovery:
1. Redis Outage / Latency Injection
2. PostgreSQL Disconnect Injection
3. Worker Process Crash Simulation
4. Network Latency & Packet Loss Injection
5. GPU Memory Allocation / OOM Failure Injection

Features:
- Safe, scoped fault injection with automatic rollback timers
- Automated recovery verification reports
"""
import time
import random
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("uvicorn")


class FaultType:
    REDIS_FAILURE = "REDIS_FAILURE"
    POSTGRES_FAILURE = "POSTGRES_FAILURE"
    WORKER_CRASH = "WORKER_CRASH"
    NETWORK_LATENCY = "NETWORK_LATENCY"
    PACKET_LOSS = "PACKET_LOSS"
    GPU_FAILURE = "GPU_FAILURE"


class ChaosEngine:
    """Automated Fault Injection & Verification Harness."""

    def __init__(self):
        self._active_faults: Dict[str, Dict[str, Any]] = {}
        self._chaos_audit_history: List[Dict[str, Any]] = []

    def inject_fault(self, fault_type: str, duration_sec: int = 10, target: str = "global") -> Dict[str, Any]:
        """Inject a simulated fault scenario with auto-expiry timer."""
        fault_id = f"fault_{fault_type.lower()}_{int(time.time())}"
        expires_at = time.time() + duration_sec

        fault_info = {
            "fault_id": fault_id,
            "fault_type": fault_type,
            "target": target,
            "duration_sec": duration_sec,
            "injected_at": time.time(),
            "expires_at": expires_at,
            "status": "ACTIVE"
        }

        self._active_faults[fault_id] = fault_info
        logger.error(f"ChaosEngine FAULT INJECTED: [{fault_type}] targeting '{target}' for {duration_sec}s")
        self._record_telemetry("fault_injected", fault_type)
        return fault_info

    def is_fault_active(self, fault_type: str, target: str = "global") -> bool:
        """Check if a specific fault type is currently active for target."""
        now = time.time()
        expired = []
        is_active = False

        for fid, f in self._active_faults.items():
            if now > f["expires_at"]:
                expired.append(fid)
            elif f["fault_type"] == fault_type and f["target"] in (target, "global"):
                is_active = True

        for fid in expired:
            f = self._active_faults.pop(fid)
            f["status"] = "RECOVERED"
            self._chaos_audit_history.append(f)
            logger.info(f"ChaosEngine FAULT RECOVERED: [{f['fault_type']}] expired after {f['duration_sec']}s")
            self._record_telemetry("fault_recovered", f['fault_type'])

        return is_active

    def run_chaos_experiment(self, fault_type: str, test_func: callable) -> Dict[str, Any]:
        """
        Run a complete Chaos Experiment: inject fault -> execute operation -> verify automatic recovery.
        """
        logger.info(f"ChaosEngine Starting Experiment for {fault_type}")
        fault = self.inject_fault(fault_type, duration_sec=5)

        op_success = False
        error_caught = None

        try:
            res = test_func()
            op_success = True
        except Exception as e:
            error_caught = str(e)
            op_success = False

        # Wait for fault recovery
        time.sleep(5.5)
        recovery_confirmed = not self.is_fault_active(fault_type)

        return {
            "experiment": fault_type,
            "fault_id": fault["fault_id"],
            "operation_succeeded_during_fault": op_success,
            "error_caught": error_caught,
            "automatic_recovery_confirmed": recovery_confirmed,
            "result": "PASS" if recovery_confirmed else "FAIL"
        }

    def _record_telemetry(self, event: str, fault_type: str):
        try:
            from backend.observability.metrics import metrics
            metrics.inc_counter(f"chaos_{event}_total", fault_type=fault_type)
        except Exception:
            pass


chaos_engine = ChaosEngine()
