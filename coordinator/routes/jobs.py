"""
Jobs router — handles job submission, sharding, status, and result download.
"""
import hashlib
import json
import os
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from aggregator import artifact_exists, artifact_path
from models import Job, Task, get_db, new_uuid
from schemas import JobCreate, JobResponse, JobDetail, TaskSummary

router = APIRouter(prefix="/jobs", tags=["jobs"])

MAX_DATASET_LINES = 50_000  # guard against huge uploads in MVP


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _shard_dataset(lines: List[str], chunk_size: int) -> List[List[str]]:
    """Split a list of lines into chunks of at most chunk_size."""
    return [lines[i : i + chunk_size] for i in range(0, len(lines), chunk_size)]


def _payload_checksum(data: List[str]) -> str:
    """SHA-256 of the JSON-serialised shard, used for integrity verification."""
    raw = json.dumps(data, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _job_to_response(job: Job) -> JobResponse:
    pct = (job.done_tasks / job.total_tasks * 100) if job.total_tasks else 0.0
    return JobResponse(
        id=job.id,
        status=job.status,
        job_type=job.job_type,
        chunk_size=job.chunk_size,
        total_tasks=job.total_tasks,
        done_tasks=job.done_tasks,
        created_at=job.created_at,
        completed_at=job.completed_at,
        progress_pct=round(pct, 2),
    )


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.post("/", response_model=JobResponse, status_code=201)
def create_job(body: JobCreate, db: Session = Depends(get_db)):
    """
    Submit a new ML job.

    The dataset is split into shards of `chunk_size` lines, each shard
    becomes a Task record in the database with status=pending.
    """
    # Parse and validate dataset
    lines = [l.strip() for l in body.dataset_text.splitlines() if l.strip()]
    if not lines:
        raise HTTPException(status_code=400, detail="Dataset is empty — no non-blank lines found.")
    if len(lines) > MAX_DATASET_LINES:
        raise HTTPException(
            status_code=400,
            detail=f"Dataset too large: {len(lines)} lines (max {MAX_DATASET_LINES}).",
        )

    # Create job
    job = Job(
        id=new_uuid(),
        status="in_progress",
        job_type=body.job_type,
        dataset_text=body.dataset_text,
        chunk_size=body.chunk_size,
        created_at=datetime.utcnow(),
    )
    db.add(job)
    db.flush()  # get job.id without committing

    # Shard dataset → Tasks
    shards = _shard_dataset(lines, body.chunk_size)
    for idx, shard in enumerate(shards):
        payload = json.dumps({"data": shard, "config": {"job_type": body.job_type}})
        task = Task(
            id=new_uuid(),
            job_id=job.id,
            task_index=idx,
            status="pending",
            payload=payload,
            checksum=_payload_checksum(shard),
            attempts=0,
        )
        db.add(task)

    job.total_tasks = len(shards)
    job.done_tasks = 0
    db.commit()
    db.refresh(job)

    return _job_to_response(job)


@router.get("/", response_model=List[JobResponse])
def list_jobs(db: Session = Depends(get_db)):
    """List all jobs, most recent first."""
    jobs = db.query(Job).order_by(Job.created_at.desc()).all()
    return [_job_to_response(j) for j in jobs]


@router.get("/{job_id}", response_model=JobDetail)
def get_job(job_id: str, db: Session = Depends(get_db)):
    """Get full job detail including per-task status."""
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    pct = (job.done_tasks / job.total_tasks * 100) if job.total_tasks else 0.0
    tasks = [
        TaskSummary(
            id=t.id,
            task_index=t.task_index,
            status=t.status,
            worker_id=t.worker_id,
            assigned_at=t.assigned_at,
            completed_at=t.completed_at,
            attempts=t.attempts,
        )
        for t in sorted(job.tasks, key=lambda t: t.task_index)
    ]

    return JobDetail(
        id=job.id,
        status=job.status,
        job_type=job.job_type,
        chunk_size=job.chunk_size,
        total_tasks=job.total_tasks,
        done_tasks=job.done_tasks,
        created_at=job.created_at,
        completed_at=job.completed_at,
        progress_pct=round(pct, 2),
        tasks=tasks,
    )


@router.get("/{job_id}/result")
def download_result(job_id: str, db: Session = Depends(get_db)):
    """
    Download the merged result artifact for a completed job.

    Returns the artifact as a JSON file download
    (Content-Disposition: attachment) so browsers and curl save it directly.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Job is not completed yet (status: {job.status}). "
                   f"Progress: {job.done_tasks}/{job.total_tasks} tasks.",
        )
    if not artifact_exists(job_id):
        raise HTTPException(
            status_code=404,
            detail="Result artifact not found on disk. "
                   "This may indicate an aggregation error — check coordinator logs.",
        )

    return FileResponse(
        path=artifact_path(job_id),
        media_type="application/json",
        filename=f"opentrain_{job_id[:8]}_{job.job_type}.json",
    )


@router.get("/{job_id}/result/summary")
def result_summary(job_id: str, db: Session = Depends(get_db)):
    """
    Return lightweight metadata about a completed job's artifact
    without streaming the full result payload.
    Useful for the dashboard to display stats before the user downloads.
    """
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job.status != "completed":
        raise HTTPException(status_code=409, detail=f"Job not completed (status: {job.status}).")
    if not artifact_exists(job_id):
        raise HTTPException(status_code=404, detail="Artifact not found on disk.")

    with open(artifact_path(job_id)) as f:
        artifact = json.load(f)

    return {
        "job_id":       job_id,
        "job_type":     artifact.get("job_type"),
        "total_tasks":  artifact.get("total_tasks"),
        "total_items":  artifact.get("total_items"),
        "wall_seconds": artifact.get("wall_seconds"),
        "completed_at": artifact.get("completed_at"),
        "artifact_size_bytes": os.path.getsize(artifact_path(job_id)),
    }