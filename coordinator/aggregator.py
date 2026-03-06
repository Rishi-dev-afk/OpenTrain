"""
aggregator.py — Merges completed task results into a final job artifact.

Called by:
  - routes/tasks.py  when the last result comes in (hot path)
  - scheduler.py     when check_stalled_jobs detects a stuck job (recovery path)

Guarantees:
  - Concurrency-safe: per-job threading lock prevents double-aggregation.
  - Atomic write: artifact written to a temp file then os.replace()'d into place.
  - Idempotent: no-ops if already completed.
"""
import json
import os
import tempfile
import threading
from datetime import datetime

from sqlalchemy.orm import Session

from models import DATA_DIR, Job, Task

RESULTS_DIR = os.path.join(DATA_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

_job_locks: dict[str, threading.Lock] = {}
_locks_mutex = threading.Lock()


def _get_job_lock(job_id: str) -> threading.Lock:
    with _locks_mutex:
        if job_id not in _job_locks:
            _job_locks[job_id] = threading.Lock()
        return _job_locks[job_id]


def _release_job_lock(job_id: str):
    with _locks_mutex:
        _job_locks.pop(job_id, None)


# ─── Public entry point ───────────────────────────────────────────────────────

def try_aggregate_job(job_id: str, db: Session) -> bool:
    lock = _get_job_lock(job_id)
    if not lock.acquire(blocking=False):
        print(f"[aggregator] Job {job_id[:8]}… aggregation already in progress, skipping.")
        return False
    try:
        return _aggregate(job_id, db)
    finally:
        lock.release()


# ─── Core aggregation ─────────────────────────────────────────────────────────

def _aggregate(job_id: str, db: Session) -> bool:
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        return False

    out_path = artifact_path(job_id)
    if job.status == "completed" and os.path.exists(out_path):
        return True

    tasks = (
        db.query(Task)
        .filter(Task.job_id == job_id)
        .order_by(Task.task_index)
        .all()
    )

    incomplete = [t for t in tasks if t.status != "completed"]
    if incomplete:
        return False

    print(f"[aggregator] Merging {len(tasks)} tasks for job {job_id[:8]}… (type={job.job_type})")
    merged, stats = _merge_results(job.job_type, tasks)

    completed_at = datetime.utcnow()
    artifact = {
        "job_id":       job_id,
        "job_type":     job.job_type,
        "total_tasks":  len(tasks),
        "total_items":  stats["total_items"],
        "completed_at": completed_at.isoformat() + "Z",
        "wall_seconds": (completed_at - job.created_at).total_seconds(),
        "result":       merged,
    }

    tmp_fd, tmp_path = tempfile.mkstemp(dir=RESULTS_DIR, suffix=".tmp")
    try:
        with os.fdopen(tmp_fd, "w") as f:
            json.dump(artifact, f)
        os.replace(tmp_path, out_path)
    except Exception as e:
        os.unlink(tmp_path)
        print(f"[aggregator] Failed to write artifact for job {job_id[:8]}…: {e}")
        return False

    job.status       = "completed"
    job.completed_at = completed_at
    db.commit()

    print(
        f"[aggregator] ✓ Job {job_id[:8]}… complete — "
        f"{stats['total_items']} items, {artifact['wall_seconds']:.1f}s wall time."
    )
    return True


# ─── Merge strategies ─────────────────────────────────────────────────────────

def _merge_results(job_type: str, tasks: list) -> tuple[list, dict]:
    merged = []
    for task in tasks:
        if not task.result:
            continue
        data = json.loads(task.result)
        if job_type == "embedding":
            items = data.get("embeddings", [])
        elif job_type in ("tokenize", "preprocess"):
            items = data.get("output", [])
        else:
            items = [{"task_index": task.task_index, "data": data}]
        merged.extend(items)
    return merged, {"total_items": len(merged)}


# ─── Artifact helpers ─────────────────────────────────────────────────────────

def artifact_path(job_id: str) -> str:
    return os.path.join(RESULTS_DIR, f"{job_id}.json")


def artifact_exists(job_id: str) -> bool:
    return os.path.exists(artifact_path(job_id))
