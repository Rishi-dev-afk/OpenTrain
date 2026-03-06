"""
Pydantic schemas for OpenTrain API request/response validation.
Kept separate from SQLAlchemy models for clean separation of concerns.
"""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional, List
from pydantic import BaseModel, Field, field_serializer


# ─── Job schemas ──────────────────────────────────────────────────────────────

class JobCreate(BaseModel):
    job_type: str = Field(..., description="embedding | tokenize | preprocess")
    dataset_text: str = Field(..., description="Raw text dataset, one item per line")
    chunk_size: int = Field(default=100, ge=1, le=5000, description="Lines per task shard")


class TaskSummary(BaseModel):
    id: str
    task_index: int
    status: str
    worker_id: Optional[str]
    assigned_at: Optional[datetime]
    completed_at: Optional[datetime]
    attempts: int

    class Config:
        from_attributes = True

    @field_serializer('assigned_at', 'completed_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Ensure datetimes are serialized with UTC timezone."""
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()


class JobResponse(BaseModel):
    id: str
    status: str
    job_type: str
    chunk_size: int
    total_tasks: int
    done_tasks: int
    created_at: datetime
    completed_at: Optional[datetime]
    progress_pct: float = 0.0

    class Config:
        from_attributes = True

    @field_serializer('created_at', 'completed_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        """Ensure datetimes are serialized with UTC timezone."""
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()


class JobDetail(JobResponse):
    tasks: List[TaskSummary] = []

    class Config:
        from_attributes = True


# ─── Task schemas ─────────────────────────────────────────────────────────────

class TaskAssignment(BaseModel):
    task_id: str
    job_id: str
    task_index: int
    job_type: str
    payload: str   # raw JSON string; worker parses it


class TaskResult(BaseModel):
    worker_id: str
    result: str    # JSON string — worker serialises its output
    checksum: str  # SHA-256 of the result for integrity verification


class TaskFailure(BaseModel):
    worker_id: str
    error: str


# ─── Worker schemas ───────────────────────────────────────────────────────────

class WorkerRegister(BaseModel):
    hostname: Optional[str] = None


class WorkerRegistered(BaseModel):
    worker_id: str
    message: str


class WorkerHeartbeat(BaseModel):
    worker_id: str


class WorkerResponse(BaseModel):
    id: str
    status: str
    last_heartbeat: datetime
    tasks_done: int
    registered_at: datetime
    hostname: Optional[str]

    class Config:
        from_attributes = True

    @field_serializer('last_heartbeat', 'registered_at')
    def serialize_datetime(self, value: datetime) -> str:
        """Ensure datetimes are serialized with UTC timezone."""
        if value.tzinfo is None:
            # If naive, assume UTC
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()