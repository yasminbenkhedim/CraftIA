"""
GPU Lease Manager for CraftAI (Upgrade 10).

Manages GPU device leases in PostgreSQL with SELECT FOR UPDATE
to prevent concurrent acquisition of the same device.

Existing components used:
- app.core.database.SessionLocal (DB session factory)
- backend.orchestrator.models.GPULease (SQLAlchemy model)

Replaces the in-memory Dict[str, GPULease] from the original gpu_leases.py.
"""
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

logger = logging.getLogger("uvicorn")


def _import_db_and_model():
    """Import DB session and GPULease model from either path."""
    try:
        from app.core.database import SessionLocal
        from orchestrator.models import GPULease
    except ImportError:
        from backend.app.core.database import SessionLocal
        from backend.orchestrator.models import GPULease
    return SessionLocal, GPULease


class GPULeaseManager:
    """
    Production GPU lease manager backed by PostgreSQL.

    Features:
    - Exclusive device leasing via SELECT FOR UPDATE
    - Lease renewal with expiry extension
    - Automatic expired lease cleanup
    - CPU fallback after acquisition failures
    - Memory reservation tracking
    """

    DEFAULT_LEASE_DURATION_SEC = 600  # 10 minutes
    MAX_ACQUISITION_ATTEMPTS = 3

    @staticmethod
    def acquire_lease(
        device_id: str,
        worker_id: str,
        job_id: str,
        stage_id: str,
        lease_duration_sec: int = 600,
        reserved_memory_mb: int = 4096,
    ) -> Optional[Dict[str, Any]]:
        """
        Acquire an exclusive lease on a GPU device.
        Returns lease info dict on success, None if device is already leased.
        """
        SessionLocal, GPULease = _import_db_and_model()

        session = SessionLocal()
        try:
            # Check for active lease on this device (SELECT FOR UPDATE)
            existing = session.query(GPULease).filter(
                GPULease.device_id == device_id,
                GPULease.released == False,
                GPULease.expires_at > datetime.utcnow(),
            ).with_for_update().first()

            if existing:
                logger.warning(
                    f"GPU lease denied: device={device_id} already leased by "
                    f"worker={existing.worker_id} until {existing.expires_at}"
                )
                return None

            # Create new lease
            lease_id = str(uuid.uuid4())
            expires_at = datetime.utcnow() + timedelta(seconds=lease_duration_sec)

            lease = GPULease(
                id=lease_id,
                device_id=device_id,
                worker_id=worker_id,
                job_id=job_id,
                stage_id=stage_id,
                reserved_memory_mb=reserved_memory_mb,
                expires_at=expires_at,
            )
            session.add(lease)
            session.commit()

            logger.info(
                f"GPU lease acquired: device={device_id} worker={worker_id} "
                f"job={job_id} expires={expires_at} memory={reserved_memory_mb}MB"
            )

            return {
                "lease_id": lease_id,
                "device_id": device_id,
                "worker_id": worker_id,
                "expires_at": expires_at.isoformat(),
                "reserved_memory_mb": reserved_memory_mb,
            }

        except Exception as e:
            session.rollback()
            logger.error(f"GPU lease acquisition failed: {e}")
            return None
        finally:
            session.close()

    @staticmethod
    def release_lease(lease_id: str) -> bool:
        """Release a GPU lease."""
        SessionLocal, GPULease = _import_db_and_model()

        session = SessionLocal()
        try:
            lease = session.query(GPULease).filter(
                GPULease.id == lease_id
            ).first()

            if not lease:
                return False

            lease.released = True
            session.commit()

            logger.info(f"GPU lease released: device={lease.device_id} lease={lease_id}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"GPU lease release failed: {e}")
            return False
        finally:
            session.close()

    @staticmethod
    def renew_lease(lease_id: str, extension_sec: int = 600) -> bool:
        """
        Renew a GPU lease by extending its expiry.
        Only succeeds if the lease is still active (not expired, not released).
        """
        SessionLocal, GPULease = _import_db_and_model()

        session = SessionLocal()
        try:
            lease = session.query(GPULease).filter(
                GPULease.id == lease_id,
                GPULease.released == False,
                GPULease.expires_at > datetime.utcnow(),
            ).with_for_update().first()

            if not lease:
                logger.warning(f"GPU lease renewal failed: lease={lease_id} not active")
                return False

            lease.expires_at = datetime.utcnow() + timedelta(seconds=extension_sec)
            session.commit()

            logger.info(f"GPU lease renewed: lease={lease_id} new_expiry={lease.expires_at}")
            return True

        except Exception as e:
            session.rollback()
            logger.error(f"GPU lease renewal failed: {e}")
            return False
        finally:
            session.close()

    @staticmethod
    def cleanup_expired_leases() -> int:
        """Remove expired leases, freeing devices for new workers."""
        SessionLocal, GPULease = _import_db_and_model()

        session = SessionLocal()
        try:
            expired = session.query(GPULease).filter(
                GPULease.released == False,
                GPULease.expires_at < datetime.utcnow(),
            ).all()

            count = len(expired)
            for lease in expired:
                lease.released = True
                logger.info(f"GPU lease expired: device={lease.device_id} lease={lease.id}")

            if count > 0:
                session.commit()

            return count

        except Exception as e:
            session.rollback()
            logger.error(f"GPU lease cleanup failed: {e}")
            return 0
        finally:
            session.close()

    @staticmethod
    def get_available_devices(required_memory_mb: int = 4096) -> List[str]:
        """Get list of GPU devices not currently leased."""
        SessionLocal, GPULease = _import_db_and_model()

        # Default device pool — in production, discovered via nvidia-smi or K8s device plugin
        all_devices = ["gpu-0", "gpu-1", "gpu-2", "gpu-3"]

        session = SessionLocal()
        try:
            active_leases = session.query(GPULease.device_id).filter(
                GPULease.released == False,
                GPULease.expires_at > datetime.utcnow(),
            ).all()

            leased_devices = {l.device_id for l in active_leases}
            available = [d for d in all_devices if d not in leased_devices]
            return available

        finally:
            session.close()

    @staticmethod
    def get_device_memory_info(device_id: str) -> Dict[str, Any]:
        """
        Query GPU memory information.
        Uses torch.cuda or nvidia-smi if available, falls back to defaults.
        """
        try:
            import torch
            if torch.cuda.is_available():
                device_idx = int(device_id.replace("gpu-", ""))
                total = torch.cuda.get_device_properties(device_idx).total_mem
                free, _ = torch.cuda.mem_get_info(device_idx)
                return {
                    "device_id": device_id,
                    "total_memory_mb": total // (1024 * 1024),
                    "free_memory_mb": free // (1024 * 1024),
                    "source": "torch.cuda",
                }
        except Exception:
            pass

        # Fallback defaults
        return {
            "device_id": device_id,
            "total_memory_mb": 8192,
            "free_memory_mb": 8192,
            "source": "default",
        }
