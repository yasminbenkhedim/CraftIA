import sys
from pathlib import Path

# Add project root to sys.path so agents module can be imported cleanly
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Load the root .env into os.environ BEFORE importing app.core.config, which
# validates required secrets at import time and reads only os.environ. This also
# makes PEXELS_API_KEY and WAV2LIP_* available to the providers/engines.
_BACKEND_DIR = str(Path(__file__).resolve().parent.parent)
if _BACKEND_DIR not in sys.path:
    sys.path.insert(0, _BACKEND_DIR)
import env_bootstrap  # noqa: F401  (side-effect: loads .env)

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.api.router import api_router

logger = logging.getLogger("uvicorn")

# Initialize database tables on startup
init_db()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Set up CORS middleware for Angular SPA frontend
# Note: allow_credentials=True requires explicit origins (not wildcard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:4200",
        "http://localhost:55422",
        "http://localhost:3000",
        "http://127.0.0.1:4200",
        "http://127.0.0.1:55422",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API Router (both /api and /api/v1 for complete frontend/v1/v2 compatibility)
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(api_router, prefix="/api/v1")

# Include Upgrade 11 Routers (v1, v2, admin)
try:
    from api.v2.router import router_v1 as v1_enterprise_router, router_v2 as v2_router
    from api.admin import admin_router
    from app.api.websocket_stream import router as ws_router
    app.include_router(v1_enterprise_router)
    app.include_router(v2_router)
    app.include_router(admin_router)
    app.include_router(ws_router)
except Exception as err:
    print(f"Warning mounting v2/admin routers: {err}")

# Health probe endpoints & Prometheus metrics
@app.get("/health/live")
def health_liveness():
    from observability.metrics import health
    return health.liveness()

@app.get("/health/ready")
def health_readiness():
    from observability.metrics import health
    return health.readiness()

@app.get("/health/startup")
def health_startup():
    from observability.metrics import health
    return health.startup()

@app.get("/metrics")
def get_prometheus_metrics():
    from fastapi.responses import Response
    from observability.metrics import metrics
    return Response(content=metrics.export(), media_type=metrics.content_type)

from fastapi import WebSocket, WebSocketDisconnect
from app.api.websocket_live import LiveWebSocketHandler
from app.api.websocket_collaboration import CollaborationWebSocketHandler

@app.websocket("/ws/v1/live-edit")
async def websocket_live_edit_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            response = LiveWebSocketHandler.handle_message(data)
            await websocket.send_json(response)
    except WebSocketDisconnect:
        pass

@app.websocket("/ws/v1/collaboration")
async def websocket_collaboration_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_text()
            response = CollaborationWebSocketHandler.handle_message(data)
            await websocket.send_json(response)
    except WebSocketDisconnect:
        pass

@app.get("/")
def read_root():
    return {
        "status": "online",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "api_v1": settings.API_V1_STR,
        "websockets": ["/ws/v1/live-edit", "/ws/v1/collaboration"]
    }

# Startup Event: Clean up orphan jobs and check storage retention
@app.on_event("startup")
def startup_cleanup_and_governance():
    import os
    import time
    from datetime import datetime
    from app.core.database import SessionLocal
    from app.models.job import Job, JobStatus

    db = SessionLocal()
    try:
        # Priority 2: Clean up orphaned QUEUED/RUNNING jobs from prior server process restart
        orphaned = db.query(Job).filter(Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value])).all()
        for j in orphaned:
            j.status = JobStatus.FAILED.value
            j.current_step = "Process restarted mid-execution (Orphaned Job Cleanup)"
            j.completed_at = datetime.utcnow()
        db.commit()
    except Exception as e:
        db.rollback()
    finally:
        db.close()

    # Priority 3: Storage retention worker.
    #
    # STORAGE_RETENTION_DAYS in .env; 0 or negative disables the sweep entirely, which is
    # what you want on a dev machine where the artifacts ARE the test corpus.
    #
    # The default used to be 7 days and the deletion was silent -- no log line, exceptions
    # swallowed -- so a machine left running for a fortnight quietly lost every earlier
    # test render and the only symptom was 404s on the dashboard thumbnails. Every
    # deletion is now logged with its reason, and the count is reported even when zero.
    retention_days = int(os.getenv("STORAGE_RETENTION_DAYS", "90"))
    storage_dir = Path(settings.STORAGE_PATH)

    if retention_days <= 0:
        logger.info(
            f"Storage retention: DISABLED (STORAGE_RETENTION_DAYS={retention_days}). "
            f"No artifacts will be deleted."
        )
    elif storage_dir.exists():
        import shutil
        cutoff_time = time.time() - (retention_days * 86400)
        removed, freed, failed = [], 0, 0
        for item in sorted(storage_dir.glob("*")):
            if not item.is_dir():
                continue
            try:
                if item.stat().st_mtime >= cutoff_time:
                    continue
                size = sum(f.stat().st_size for f in item.rglob("*") if f.is_file())
                age_days = (time.time() - item.stat().st_mtime) / 86400.0
                shutil.rmtree(item)
                removed.append(item.name)
                freed += size
                logger.info(
                    f"Storage retention: deleted {item.name} "
                    f"({age_days:.0f} days old, {size / 1048576:.1f} MB)"
                )
            except Exception as e:
                failed += 1
                logger.warning(f"Storage retention: could not remove {item.name} ({e}).")
        logger.info(
            f"Storage retention: {len(removed)} directory(ies) removed, "
            f"{freed / 1048576:.1f} MB freed, {failed} failure(s), "
            f"keeping anything newer than {retention_days} days."
        )

    # Priority 3b: flag jobs whose artifact is no longer on disk.
    #
    # Runs regardless of whether the sweep above deleted anything, so it also catches
    # files removed by hand, by an earlier build's shorter retention, or by a wiped
    # storage volume. Without this the UI keeps offering a download button that can only
    # 404 -- the record says COMPLETED, but there is nothing left to deliver.
    try:
        db = SessionLocal()
        try:
            stamped = 0
            completed = db.query(Job).filter(Job.status == JobStatus.COMPLETED.value).all()
            for j in completed:
                gone = not j.artifact_path or not os.path.exists(j.artifact_path)
                if gone and j.artifact_expired_at is None:
                    j.artifact_expired_at = datetime.utcnow()
                    stamped += 1
                elif not gone and j.artifact_expired_at is not None:
                    # The file came back (restored from a backup, or re-rendered). Clear
                    # the flag rather than leaving the job permanently marked expired.
                    j.artifact_expired_at = None
                    stamped += 1
            if stamped:
                db.commit()
                logger.info(f"Storage retention: reconciled artifact availability on {stamped} job(s).")
        finally:
            db.close()
    except Exception as e:
        logger.warning(f"Storage retention: could not reconcile job artifact flags ({e}).")

    # Priority 4: Mark Observability health probes started
    try:
        from observability.metrics import health
        health.mark_started()
    except Exception:
        pass


@app.get("/health")
def health_check():
    return {
        "status": "online",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
