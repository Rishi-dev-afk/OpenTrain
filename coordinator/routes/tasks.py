"""
Tasks router — the core of the distributed queue.

GET  /tasks/next                  → Worker pulls next pending task
POST /tasks/{task_id}/result      → Worker submits completed result
POST /tasks/{task_id}/fail        → Worker reports failure
"""
import hashlib
import json
import os
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models import Job, Task, Worker, get_db
from schemas import TaskAssignment, TaskFailure, TaskResult
from aggregator import try_aggregate_job

router = APIRouter(prefix="/tasks", tags=["tasks"])

MAX_TASK_ATTEMPTS = 3


# ─── GET /tasks/next ──────────────────────────────────────────────────────────

@router.get("/next", response_model=TaskAssignment | None)
def get_next_task(worker_id: str, db: Session = Depends(get_db)):
    """
    Worker calls this to receive its next unit of work.

    - Finds the oldest pending task (FIFO)
    - Marks it assigned with this worker_id
    - Returns task payload for the worker to process

    Returns null (204) if no tasks are currently available.
    """
    # Verify worker exists
    worker = db.query(Worker).filter(Worker.id == worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not registered.")
    if worker.status == "offline":
        raise HTTPException(status_code=403, detail="Worker is marked offline. Re-register.")

    # Find oldest pending task (FIFO by task_index within a job, then job creation order)
    task = (
        db.query(Task)
        .filter(Task.status == "pending")
        .order_by(Task.id)   # insertion order = creation order for UUIDs at this scale
        .first()
    )

    if not task:
        # Update worker to idle if it was busy
        worker.status = "idle"
        db.commit()
        return None

    # Assign task to worker
    task.status = "assigned"
    task.worker_id = worker_id
    task.assigned_at = datetime.utcnow()
    task.attempts += 1
    worker.status = "busy"
    db.commit()

    job = db.query(Job).filter(Job.id == task.job_id).first()

    return TaskAssignment(
        task_id=task.id,
        job_id=task.job_id,
        task_index=task.task_index,
        job_type=job.job_type,
        payload=task.payload,
    )


# ─── POST /tasks/{task_id}/result ─────────────────────────────────────────────

@router.post("/{task_id}/result")
def submit_result(task_id: str, body: TaskResult, db: Session = Depends(get_db)):
    """
    Worker submits the result for a completed task.

    - Verifies the submitting worker owns this task
    - Validates result checksum
    - Marks task completed and updates job progress
    - Triggers aggregation if all tasks for the job are done
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    # Idempotency: if already completed, silently accept
    if task.status == "completed":
        return {"status": "ok", "message": "Task already completed (duplicate submission ignored)."}

    if task.worker_id != body.worker_id:
        raise HTTPException(
            status_code=403,
            detail="Worker ID mismatch — this task is assigned to a different worker.",
        )

    # Checksum validation
    result_data = json.loads(body.result)
    computed = hashlib.sha256(
        json.dumps(result_data, sort_keys=True).encode()
    ).hexdigest()
    if computed != body.checksum:
        raise HTTPException(
            status_code=400,
            detail=f"Checksum mismatch. Expected {body.checksum}, got {computed}.",
        )

    # Mark task complete
    task.status = "completed"
    task.result = body.result
    task.completed_at = datetime.utcnow()

    # Update worker
    worker = db.query(Worker).filter(Worker.id == body.worker_id).first()
    if worker:
        worker.tasks_done += 1
        worker.status = "idle"

    # Update job progress
    job = db.query(Job).filter(Job.id == task.job_id).first()
    job.done_tasks += 1

    db.commit()

    # Check if all tasks for this job are done → trigger aggregation
    if job.done_tasks >= job.total_tasks:
        try_aggregate_job(job.id, db)

    return {"status": "ok", "task_id": task_id, "job_progress": f"{job.done_tasks}/{job.total_tasks}"}


# ─── POST /tasks/{task_id}/fail ───────────────────────────────────────────────

@router.post("/{task_id}/fail")
def fail_task(task_id: str, body: TaskFailure, db: Session = Depends(get_db)):
    """
    Worker reports that it could not complete a task.

    - If under MAX_TASK_ATTEMPTS: returns task to pending queue
    - If at MAX_TASK_ATTEMPTS: marks task failed, flags job
    """
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")

    if task.worker_id != body.worker_id:
        raise HTTPException(status_code=403, detail="Worker ID mismatch.")

    worker = db.query(Worker).filter(Worker.id == body.worker_id).first()
    if worker:
        worker.status = "idle"

    if task.attempts >= MAX_TASK_ATTEMPTS:
        task.status = "failed"
        job = db.query(Job).filter(Job.id == task.job_id).first()
        job.status = "failed"
        db.commit()
        return {
            "status": "failed",
            "message": f"Task exceeded max attempts ({MAX_TASK_ATTEMPTS}). Job marked failed.",
        }

    # Return to queue
    task.status = "pending"
    task.worker_id = None
    task.assigned_at = None
    db.commit()

    return {
        "status": "requeued",
        "message": f"Task returned to queue (attempt {task.attempts}/{MAX_TASK_ATTEMPTS}).",
        "error": body.error,
    }