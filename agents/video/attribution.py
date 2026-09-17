"""
AttributionRecorder -- per-job provenance manifest for every third-party asset used.

Why this exists (LICENSES.md R5 / ATTRIBUTIONS.md)
--------------------------------------------------
Attribution strings were previously built by the providers, carried on the in-memory
MediaCandidate, and then discarded -- nothing was ever written to disk. That was
survivable only because the Openverse query is pinned to `license=cc0,pdm`, neither of
which legally requires credit. The moment the allowlist widens to CC-BY, attribution
becomes mandatory and there would be no record of which asset went into which video,
and no way to answer a takedown or provenance question after the fact.

This module records every asset actually composited into a render and writes
`attributions.json` next to the finished deliverable.

Concurrency
-----------
Renders run on FastAPI's BackgroundTasks threadpool, so several jobs can be in flight in
one process. State is therefore thread-local: `start_run()` at the top of a render binds
a fresh buffer to the calling thread, and `record()` writes only into that thread's
buffer. A job that never calls `start_run()` records nothing rather than leaking entries
into a neighbouring job's manifest.
"""
import os
import json
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("uvicorn")

MANIFEST_NAME = "attributions.json"

# Providers whose output we generated or own; no third-party credit applies.
_SELF_OWNED = frozenset({
    "local_asset", "procedural_overlay", "procedural_background",
    "procedural", "user_upload",
})

# Canonical licence URLs, keyed by the LicenseType value recorded on the asset.
_LICENSE_URLS = {
    "cc0": "https://creativecommons.org/publicdomain/zero/1.0/",
    "pdm": "https://creativecommons.org/publicdomain/mark/1.0/",
    "cc_by": "https://creativecommons.org/licenses/by/4.0/",
    "pexels_free": "https://www.pexels.com/license/",
}

_local = threading.local()


def start_run(run_id: Optional[str] = None) -> None:
    """Begins a fresh manifest for the calling thread. Safe to call more than once."""
    _local.entries = []
    _local.run_id = run_id
    _local.seen = set()


def _buffer() -> Optional[List[Dict[str, Any]]]:
    return getattr(_local, "entries", None)


def record(candidate: Any, scene_id: str = "", license_type: str = "") -> None:
    """
    Records one asset actually used in the render.

    Silently no-ops when the candidate is procedural/self-owned or when no run is
    active -- recording must never be able to fail a render.
    """
    entries = _buffer()
    if entries is None or candidate is None:
        return

    try:
        provider = (getattr(candidate, "provider_id", "") or "").strip().lower()
        if not provider or provider in _SELF_OWNED:
            return

        meta = getattr(candidate, "generation_metadata", None) or {}
        asset_path = getattr(candidate, "asset_path", None)
        source_url = getattr(candidate, "remote_url", None)

        # De-duplicate: the same stock clip can back several scenes.
        key = (provider, source_url or asset_path or "", scene_id)
        seen = getattr(_local, "seen", None)
        if seen is not None:
            if key in seen:
                return
            seen.add(key)

        entries.append({
            "scene_id": scene_id or None,
            "provider": provider,
            "source_url": source_url,
            "asset_file": os.path.basename(asset_path) if asset_path else None,
            "creator": meta.get("creator") or meta.get("photographer") or meta.get("videographer"),
            "title": meta.get("title"),
            "license": getattr(candidate, "license_name", None),
            "license_type": license_type or None,
            "license_url": _LICENSE_URLS.get(license_type or ""),
            "attribution": getattr(candidate, "attribution", None),
            "attribution_required": (license_type or "") == "cc_by",
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        })
    except Exception as e:
        logger.warning(f"AttributionRecorder: could not record asset ({type(e).__name__}: {e}).")


def entries() -> List[Dict[str, Any]]:
    return list(_buffer() or [])


def flush(dest_dir: str, job_id: Optional[str] = None) -> Optional[str]:
    """
    Writes `attributions.json` into `dest_dir` and returns its path.

    Always writes, even with zero third-party assets: an empty manifest is a positive
    record that the render used only self-owned media, which is materially different
    from no manifest at all.
    """
    recorded = _buffer()
    if recorded is None:
        return None

    try:
        os.makedirs(dest_dir, exist_ok=True)
        needs_credit = [e for e in recorded if e.get("attribution_required")]
        payload = {
            "job_id": job_id,
            "run_id": getattr(_local, "run_id", None),
            "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "policy": "commercial-use allowlist: cc0, pdm, cc-by (with credit), pexels",
            "asset_count": len(recorded),
            "attribution_required_count": len(needs_credit),
            "assets": recorded,
        }
        path = os.path.join(dest_dir, MANIFEST_NAME)
        tmp = f"{path}.part"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
        logger.info(
            f"AttributionRecorder: wrote {len(recorded)} asset record(s) "
            f"({len(needs_credit)} needing credit) -> {path}"
        )
        return path
    except Exception as e:
        logger.warning(f"AttributionRecorder: could not write manifest ({type(e).__name__}: {e}).")
        return None
