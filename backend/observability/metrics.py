"""
CraftAI Production Observability Module — Upgrade 10.

Provides real Prometheus metrics, OpenTelemetry tracing, structured JSON logging,
health probe endpoints, and audit logging.

Existing components used:
- backend.app.core.database (SessionLocal — health check)
- backend.app.core.config (Settings)

Integration points:
- FastAPI middleware for request tracing
- Health endpoints mounted on FastAPI app
- Prometheus /metrics endpoint
- OpenTelemetry TracerProvider for distributed tracing

Why new module:
- No observability infrastructure existed in CraftAI
- Production deployment requires health probes, metrics, and tracing
"""
import os
import time
import json
import uuid
import logging
import platform
from datetime import datetime
from typing import Dict, Any, Optional, List
from enum import Enum


# ============================================================
# STRUCTURED JSON LOGGING
# ============================================================

class StructuredLogger:
    """
    Production-grade structured logger that emits JSON-formatted log entries
    with trace context propagation.
    """

    def __init__(self, service_name: str = "craftai"):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)

    def log(self, level: str, message: str, **context):
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level.upper(),
            "service": self.service_name,
            "message": message,
            "hostname": platform.node(),
        }
        entry.update(context)
        log_line = json.dumps(entry, default=str)

        log_func = getattr(self.logger, level.lower(), self.logger.info)
        log_func(log_line)
        return entry

    def info(self, message: str, **ctx):
        return self.log("info", message, **ctx)

    def warning(self, message: str, **ctx):
        return self.log("warning", message, **ctx)

    def error(self, message: str, **ctx):
        return self.log("error", message, **ctx)


# ============================================================
# PROMETHEUS METRICS
# ============================================================

class MetricType(str, Enum):
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"


class PrometheusMetrics:
    """
    Production Prometheus metrics collector.

    Uses prometheus_client library if available, falls back to
    custom implementation for environments without the library.

    Label cardinality is strictly bounded — no job_id, tenant_id,
    or worker_id labels to prevent metric explosion.
    """

    def __init__(self):
        self._counters: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._gauges: Dict[str, float] = {}
        self._use_native = False

        try:
            from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
            self._native_counters = {}
            self._native_histograms = {}
            self._native_gauges = {}
            self._generate_latest = generate_latest
            self._content_type = CONTENT_TYPE_LATEST
            self._use_native = True

            # Define production metrics
            self._native_counters["jobs_total"] = Counter(
                "craftai_jobs_total", "Total jobs processed",
                ["status"]
            )
            self._native_counters["stages_total"] = Counter(
                "craftai_stages_total", "Total stages executed",
                ["stage", "result"]
            )
            self._native_counters["artifacts_total"] = Counter(
                "craftai_artifacts_total", "Total artifacts stored",
                ["retention_class"]
            )
            self._native_histograms["stage_duration_seconds"] = Histogram(
                "craftai_stage_duration_seconds", "Stage execution duration",
                ["stage"],
                buckets=[0.1, 0.5, 1, 2, 5, 10, 30, 60, 120, 300, 600]
            )
            self._native_histograms["job_duration_seconds"] = Histogram(
                "craftai_job_duration_seconds", "Total job duration",
                buckets=[1, 5, 10, 30, 60, 120, 300, 600, 1800]
            )
            self._native_gauges["active_workers"] = Gauge(
                "craftai_active_workers", "Currently active workers",
                ["role"]
            )
            self._native_gauges["gpu_leases_active"] = Gauge(
                "craftai_gpu_leases_active", "Active GPU leases"
            )
            self._native_gauges["queue_depth"] = Gauge(
                "craftai_queue_depth", "Tasks in queue",
                ["queue"]
            )

        except ImportError:
            pass  # Use fallback implementation

    def inc_counter(self, name: str, value: float = 1.0, **labels):
        if self._use_native and name in self._native_counters:
            label_values = tuple(labels.values()) if labels else ()
            self._native_counters[name].labels(*label_values).inc(value)
        else:
            key = f"{name}:{json.dumps(labels, sort_keys=True)}"
            self._counters[key] = self._counters.get(key, 0) + value

    def observe_histogram(self, name: str, value: float, **labels):
        if self._use_native and name in self._native_histograms:
            label_values = tuple(labels.values()) if labels else ()
            self._native_histograms[name].labels(*label_values).observe(value)
        else:
            key = f"{name}:{json.dumps(labels, sort_keys=True)}"
            if key not in self._histograms:
                self._histograms[key] = []
            self._histograms[key].append(value)

    def set_gauge(self, name: str, value: float, **labels):
        if self._use_native and name in self._native_gauges:
            label_values = tuple(labels.values()) if labels else ()
            self._native_gauges[name].labels(*label_values).set(value)
        else:
            key = f"{name}:{json.dumps(labels, sort_keys=True)}"
            self._gauges[key] = value

    def export(self) -> bytes:
        """Export metrics in Prometheus exposition format."""
        if self._use_native:
            return self._generate_latest()

        # Fallback: generate text format manually
        lines = []
        for key, val in self._counters.items():
            name, labels_json = key.split(":", 1)
            labels = json.loads(labels_json)
            label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
            metric_name = f"craftai_{name}"
            if label_str:
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(f"{metric_name}{{{label_str}}} {val}")
            else:
                lines.append(f"# TYPE {metric_name} counter")
                lines.append(f"{metric_name} {val}")

        for key, val in self._gauges.items():
            name, labels_json = key.split(":", 1)
            labels = json.loads(labels_json)
            label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
            metric_name = f"craftai_{name}"
            lines.append(f"# TYPE {metric_name} gauge")
            if label_str:
                lines.append(f"{metric_name}{{{label_str}}} {val}")
            else:
                lines.append(f"{metric_name} {val}")

        return "\n".join(lines).encode("utf-8")

    @property
    def content_type(self) -> str:
        if self._use_native:
            return self._content_type
        return "text/plain; version=0.0.4; charset=utf-8"


# ============================================================
# OPENTELEMETRY TRACING
# ============================================================

class TracingProvider:
    """
    OpenTelemetry tracing integration.

    Uses opentelemetry-sdk if available, falls back to a lightweight
    trace context propagation using trace_id fields.
    """

    def __init__(self, service_name: str = "craftai"):
        self.service_name = service_name
        self._tracer = None
        self._use_otel = False

        try:
            from opentelemetry import trace
            from opentelemetry.sdk.trace import TracerProvider
            from opentelemetry.sdk.resources import Resource

            resource = Resource.create({"service.name": service_name})
            provider = TracerProvider(resource=resource)

            # Try to add OTLP exporter if endpoint configured
            otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
            if otlp_endpoint:
                try:
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
                    from opentelemetry.sdk.trace.export import BatchSpanProcessor
                    exporter = OTLPSpanExporter(endpoint=otlp_endpoint)
                    provider.add_span_processor(BatchSpanProcessor(exporter))
                except ImportError:
                    pass

            trace.set_tracer_provider(provider)
            self._tracer = trace.get_tracer(service_name)
            self._use_otel = True

        except ImportError:
            pass

    def start_span(self, name: str, **attributes):
        """Start a trace span. Returns a context manager."""
        if self._use_otel and self._tracer:
            span = self._tracer.start_span(name, attributes=attributes)
            return span
        return _NoOpSpan(name)

    def generate_trace_id(self) -> str:
        """Generate a W3C-compatible trace ID."""
        return uuid.uuid4().hex


class _NoOpSpan:
    """Lightweight span substitute when OpenTelemetry is not available."""

    def __init__(self, name: str):
        self.name = name
        self.start_time = time.time()

    def set_attribute(self, key: str, value: Any):
        pass

    def set_status(self, status):
        pass

    def end(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.end()


# ============================================================
# HEALTH PROBES
# ============================================================

class HealthStatus(str, Enum):
    UP = "UP"
    DOWN = "DOWN"
    STARTING = "STARTING"
    DEGRADED = "DEGRADED"


class HealthProbes:
    """
    Kubernetes-compatible health probe endpoints.

    /health/live — Is the process alive?
    /health/ready — Can the service handle requests?
    /health/startup — Has initialization completed?

    Checks database, Redis, and filesystem health.
    """

    def __init__(self):
        self._started = False
        self._dependencies: Dict[str, HealthStatus] = {}

    def mark_started(self):
        self._started = True

    def set_dependency_status(self, name: str, status: HealthStatus):
        self._dependencies[name] = status

    def check_database(self) -> bool:
        """Check PostgreSQL connectivity using existing SessionLocal."""
        try:
            from backend.app.core.database import SessionLocal
            session = SessionLocal()
            session.execute("SELECT 1")
            session.close()
            self.set_dependency_status("postgres", HealthStatus.UP)
            return True
        except Exception:
            self.set_dependency_status("postgres", HealthStatus.DOWN)
            return False

    def check_redis(self) -> bool:
        """Check Redis connectivity."""
        try:
            import redis
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            r = redis.from_url(redis_url, socket_timeout=2)
            r.ping()
            self.set_dependency_status("redis", HealthStatus.UP)
            return True
        except Exception:
            self.set_dependency_status("redis", HealthStatus.DOWN)
            return False

    def check_storage(self) -> bool:
        """Check artifact storage filesystem."""
        try:
            storage_path = os.getenv("STORAGE_PATH", "./storage/artifacts")
            os.makedirs(storage_path, exist_ok=True)
            test_file = os.path.join(storage_path, ".health_check")
            with open(test_file, "w") as f:
                f.write(str(time.time()))
            os.remove(test_file)
            self.set_dependency_status("storage", HealthStatus.UP)
            return True
        except Exception:
            self.set_dependency_status("storage", HealthStatus.DOWN)
            return False

    def liveness(self) -> Dict[str, Any]:
        """Process is alive."""
        return {
            "status": HealthStatus.UP.value,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def readiness(self) -> Dict[str, Any]:
        """Service can handle requests — all dependencies healthy."""
        db_ok = self.check_database()
        redis_ok = self.check_redis()
        storage_ok = self.check_storage()

        all_ok = db_ok and storage_ok  # Redis is soft dependency
        status = HealthStatus.UP if all_ok else HealthStatus.DOWN
        if all_ok and not redis_ok:
            status = HealthStatus.DEGRADED

        return {
            "status": status.value,
            "dependencies": {k: v.value for k, v in self._dependencies.items()},
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    def startup(self) -> Dict[str, Any]:
        """Initialization complete."""
        return {
            "status": HealthStatus.UP.value if self._started else HealthStatus.STARTING.value,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }


# ============================================================
# AUDIT LOGGER
# ============================================================

class AuditLogger:
    """
    Security audit event logger.

    Persists audit events to the AuditEvent table in PostgreSQL.
    Falls back to structured logging if DB is unavailable.
    """

    def __init__(self):
        self.structured_logger = StructuredLogger("craftai.audit")

    def log_event(
        self,
        event_type: str,
        actor: str,
        resource_type: str,
        resource_id: str,
        action: str,
        result: str,
        trace_id: str = "",
        tenant_id: str = "",
        details: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        event = {
            "id": str(uuid.uuid4()),
            "event_type": event_type,
            "actor": actor,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "result": result,
            "trace_id": trace_id,
            "tenant_id": tenant_id,
            "details": details or {},
            "created_at": datetime.utcnow().isoformat() + "Z",
        }

        # Try to persist to DB
        try:
            from backend.app.core.database import SessionLocal
            from backend.orchestrator.models import AuditEvent as AuditEventModel
            session = SessionLocal()
            db_event = AuditEventModel(
                id=event["id"],
                event_type=event_type,
                actor=actor,
                resource_type=resource_type,
                resource_id=resource_id,
                action=action,
                result=result,
                trace_id=trace_id,
                tenant_id=tenant_id,
                details=details,
                created_at=datetime.utcnow(),
            )
            session.add(db_event)
            session.commit()
            session.close()
        except Exception:
            # Fall back to structured log
            self.structured_logger.info("audit_event", **event)

        return event


# ============================================================
# SINGLETON INSTANCES
# ============================================================

metrics = PrometheusMetrics()
tracer = TracingProvider()
health = HealthProbes()
audit = AuditLogger()
structured_log = StructuredLogger()
