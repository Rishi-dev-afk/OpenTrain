"""
Workers router — handles volunteer worker registration and heartbeats.
"""
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from models import Worker, get_db, new_uuid
from schemas import WorkerHeartbeat, WorkerRegister, WorkerRegistered, WorkerResponse

router = APIRouter(prefix="/workers", tags=["workers"])


@router.post("/register", response_model=WorkerRegistered, status_code=201)
def register_worker(body: WorkerRegister, db: Session = Depends(get_db)):
    """
    Volunteer machine registers itself with the coordinator.
    Returns a worker_id the client must include in all subsequent calls.
    """
    worker = Worker(
        id=new_uuid(),
        status="idle",
        hostname=body.hostname,
        registered_at=datetime.utcnow(),
        last_heartbeat=datetime.utcnow(),
    )
    db.add(worker)
    db.commit()

    return WorkerRegistered(
        worker_id=worker.id,
        message=f"Registered successfully. Poll GET /tasks/next?worker_id={worker.id} to begin.",
    )


@router.post("/heartbeat")
def heartbeat(body: WorkerHeartbeat, db: Session = Depends(get_db)):
    """
    Worker signals it is still alive.
    Called every ~30 seconds by the worker client.
    """
    worker = db.query(Worker).filter(Worker.id == body.worker_id).first()
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found. Re-register.")

    worker.last_heartbeat = datetime.utcnow()
    if worker.status == "offline":
        worker.status = "idle"   # revive worker if it reconnects
    db.commit()

    return {"status": "ok", "worker_id": body.worker_id}


@router.get("/", response_model=List[WorkerResponse])
def list_workers(db: Session = Depends(get_db)):
    """List all registered workers and their current status."""
    workers = db.query(Worker).order_by(Worker.registered_at.desc()).all()
    return [
        WorkerResponse(
            id=w.id,
            status=w.status,
            last_heartbeat=w.last_heartbeat,
            tasks_done=w.tasks_done,
            registered_at=w.registered_at,
            hostname=w.hostname,
        )
        for w in workers
    ]