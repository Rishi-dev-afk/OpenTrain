"""
Jobs router — handles job submission, sharding, status, and result download.
"""
import hashlib
import json
import os
import csv
import io
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy.orm import Session

from aggregator import artifact_exists, artifact_path
from models import Job, Task, get_db, new_uuid
from schemas import JobCreate, JobResponse, JobDetail, TaskSummary

router = APIRouter(prefix="/jobs", tags=["jobs"])

MAX_DATASET_LINES = 50_000  # guard against huge uploads in MVP
TEXT_BASED_JOBS = {"embedding", "sentiment", "tokenize", "preprocess"}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _extract_text_from_dict(item: dict) -> str:
    """
    Extract text from a dict for text-based jobs.
    Priority: "text" field → first string-valued field → JSON stringify.
    """
    if isinstance(item, str):
        return item
    if not isinstance(item, dict):
        return str(item)
    
    # Try "text" field first
    if "text" in item and isinstance(item["text"], str):
        return item["text"]
    
    # Try "content", "message", "input" fields
    for key in ["content", "message", "input", "data", "value"]:
        if key in item and isinstance(item[key], str):
            return item[key]
    
    # Fall back to first string-valued field
    for value in item.values():
        if isinstance(value, str):
            return value
    
    # Last resort: stringify the whole dict
    return json.dumps(item)


def _shard_dataset(lines: List[str], chunk_size: int) -> List[List[str]]:
    """Split a list of lines into chunks of at most chunk_size."""
    return [lines[i : i + chunk_size] for i in range(0, len(lines), chunk_size)]


def _shard_structured_data(data: List[dict], chunk_size: int) -> List[str]:
    """Shard structured data and return as JSON payloads."""
    shards = []
    for i in range(0, len(data), chunk_size):
        shard = data[i : i + chunk_size]
        shards.append(json.dumps(shard))
    return shards


def _payload_checksum(data: List[str] | str) -> str:
    """SHA-256 of the JSON-serialised shard, used for integrity verification."""
    if isinstance(data, str):
        raw = data.encode()
    else:
        raw = json.dumps(data, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _parse_csv_data(csv_text: str) -> List[dict]:
    """Parse CSV text into list of dicts."""
    if not csv_text or not csv_text.strip():
        return []
    reader = csv.DictReader(io.StringIO(csv_text))
    return list(reader) if reader else []


def _parse_json_data(json_text: str) -> List[dict]:
    """Parse JSON text into list of dicts."""
    if not json_text or not json_text.strip():
        return []
    try:
        data = json.loads(json_text)
    except (json.JSONDecodeError, ValueError):
        raise ValueError("Invalid JSON format")
    if isinstance(data, dict):
        return [data]
    elif isinstance(data, list):
        return data
    else:
        raise ValueError("JSON must be an object or array")


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
def create_job(
    file: UploadFile = File(...),
    job_type: str = Form(...),
    chunk_size: int = Form(default=100),
    data_format: str = Form(default="text"),
    config: str = Form(default="{}"),
    db: Session = Depends(get_db)
):
    """
    Submit a new ML job by uploading a file.

    The dataset is split into shards of `chunk_size` lines/rows, each shard
    becomes a Task record in the database with status=pending.
    """
    # Read and validate file content
    try:
        dataset_text = file.file.read().decode('utf-8')
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
    
    if not dataset_text or not dataset_text.strip():
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    
    # Parse config — handle empty strings and None gracefully
    if not config or not config.strip():
        job_config = {}
    else:
        try:
            job_config = json.loads(config)
        except (json.JSONDecodeError, ValueError):
            job_config = {}
    
    if data_format == "csv":
        # Parse CSV data
        rows = _parse_csv_data(dataset_text)
        if not rows:
            raise HTTPException(status_code=400, detail="CSV is empty.")
        if len(rows) > MAX_DATASET_LINES:
            raise HTTPException(
                status_code=400,
                detail=f"Dataset too large: {len(rows)} rows (max {MAX_DATASET_LINES}).",
            )
        # Convert rows to text representation for stats task
        if job_type == "stats":
            # For stats, send the CSV rows as raw dicts (not JSON-stringified)
            # so the worker can analyze all columns, not just a text field
            shards = _shard_structured_data(rows, chunk_size)
        else:
            lines = [json.dumps(row) for row in rows]
            shards = _shard_dataset(lines, chunk_size)
        
    elif data_format == "json":
        # Parse JSON data
        data = _parse_json_data(dataset_text)
        if not data:
            raise HTTPException(status_code=400, detail="JSON is empty.")
        if len(data) > MAX_DATASET_LINES:
            raise HTTPException(
                status_code=400,
                detail=f"Dataset too large: {len(data)} items (max {MAX_DATASET_LINES}).",
            )
        shards = _shard_structured_data(data, chunk_size)
        
    else:  # text format (default)
        lines = [l.strip() for l in dataset_text.splitlines() if l.strip()]
        if not lines:
            raise HTTPException(status_code=400, detail="Dataset is empty — no non-blank lines found.")
        if len(lines) > MAX_DATASET_LINES:
            raise HTTPException(
                status_code=400,
                detail=f"Dataset too large: {len(lines)} lines (max {MAX_DATASET_LINES}).",
            )
        shards = _shard_dataset(lines, chunk_size)

    # Create job
    job = Job(
        id=new_uuid(),
        status="in_progress",
        job_type=job_type,
        dataset_text=dataset_text[:1000],  # Store first 1000 chars for reference
        chunk_size=chunk_size,
        data_format=data_format,
        config=json.dumps(job_config) if job_config else None,
        created_at=datetime.utcnow(),
    )
    db.add(job)
    db.flush()  # get job.id without committing

    # Shard dataset → Tasks
    for idx, shard in enumerate(shards):
        try:
            if data_format == "csv" and job_type != "stats":
                # CSV for text-based jobs: shard is list of JSON-stringified dicts
                payloads = []
                for item in shard:
                    if not item or not item.strip():
                        continue
                    try:
                        payloads.append(json.loads(item))
                    except (json.JSONDecodeError, ValueError) as e:
                        print(f"[jobs] Warning: Skipping malformed JSON in CSV shard {idx}: {e}")
                        continue
                if not payloads:
                    raise HTTPException(status_code=400, detail=f"CSV shard {idx} has no valid rows")
            elif data_format == "csv" and job_type == "stats":
                # CSV for stats: shard is JSON array (from _shard_structured_data)
                if not shard or not shard.strip():
                    raise HTTPException(status_code=400, detail=f"Stats CSV shard {idx} is empty")
                try:
                    payloads = json.loads(shard)
                except (json.JSONDecodeError, ValueError) as e:
                    raise HTTPException(status_code=400, detail=f"Stats CSV shard {idx} is malformed: {str(e)}")
                if not isinstance(payloads, list):
                    payloads = [payloads]
            elif data_format == "json":
                # JSON: shard is a JSON array string
                if not shard or not shard.strip():
                    raise HTTPException(status_code=400, detail=f"JSON shard {idx} is empty")
                try:
                    payloads = json.loads(shard)
                except (json.JSONDecodeError, ValueError) as e:
                    raise HTTPException(status_code=400, detail=f"JSON shard {idx} is malformed: {str(e)}")
                if not isinstance(payloads, list):
                    payloads = [payloads]
            else:
                # Text format: shard is plain text list
                payloads = shard if isinstance(shard, list) else shard.split('\n') if job_type == "stats" else [shard]
        except HTTPException:
            raise
        except Exception as e:
            print(f"[jobs] Error processing shard {idx}: {e}")
            raise

        # For text-based jobs with structured data, extract text from dicts
        if job_type in TEXT_BASED_JOBS and data_format in ("csv", "json"):
            payloads = [_extract_text_from_dict(item) for item in payloads]

        payload = json.dumps({"data": payloads, "config": {"job_type": job_type, **job_config}})
        task = Task(
            id=new_uuid(),
            job_id=job.id,
            task_index=idx,
            status="pending",
            payload=payload,
            checksum=_payload_checksum(payload),
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