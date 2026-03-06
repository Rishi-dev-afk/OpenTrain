"""
Database models and session management for OpenTrain coordinator.
Uses SQLite via SQLAlchemy for MVP simplicity.

Deployment note (Render):
  DB is written to DATA_DIR which resolves to /app/data — the Render
  persistent disk mount path. This survives service restarts.
  Change DATABASE_URL to a Postgres connection string to migrate off SQLite.
"""
import os
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, DateTime, Float, ForeignKey, Integer, String, Text, create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

# ─── Storage paths ────────────────────────────────────────────────────────────

DATA_DIR = os.environ.get("DATA_DIR", "./data")
os.makedirs(DATA_DIR, exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR}/opentrain.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def new_uuid() -> str:
    return str(uuid.uuid4())


# ─── Job ──────────────────────────────────────────────────────────────────────

class Job(Base):
    __tablename__ = "jobs"

    id           = Column(String, primary_key=True, default=new_uuid)
    status       = Column(String, default="pending")      # pending | in_progress | completed | failed
    job_type     = Column(String, nullable=False)
    dataset_text = Column(Text, nullable=True)
    chunk_size   = Column(Integer, default=100)
    total_tasks  = Column(Integer, default=0)
    done_tasks   = Column(Integer, default=0)
    created_at   = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    tasks = relationship("Task", back_populates="job", cascade="all, delete-orphan")


# ─── Task ─────────────────────────────────────────────────────────────────────

class Task(Base):
    __tablename__ = "tasks"

    id           = Column(String, primary_key=True, default=new_uuid)
    job_id       = Column(String, ForeignKey("jobs.id"), nullable=False)
    task_index   = Column(Integer, nullable=False)
    status       = Column(String, default="pending")      # pending | assigned | completed | failed
    worker_id    = Column(String, ForeignKey("workers.id"), nullable=True)
    payload      = Column(Text, nullable=False)
    result       = Column(Text, nullable=True)
    checksum     = Column(String, nullable=True)
    assigned_at  = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    attempts     = Column(Integer, default=0)

    job    = relationship("Job", back_populates="tasks")
    worker = relationship("Worker", back_populates="tasks")


# ─── Worker ───────────────────────────────────────────────────────────────────

class Worker(Base):
    __tablename__ = "workers"

    id             = Column(String, primary_key=True, default=new_uuid)
    status         = Column(String, default="idle")       # idle | busy | offline
    last_heartbeat = Column(DateTime, default=datetime.utcnow)
    tasks_done     = Column(Integer, default=0)
    registered_at  = Column(DateTime, default=datetime.utcnow)
    hostname       = Column(String, nullable=True)

    tasks = relationship("Task", back_populates="worker")


def create_tables():
    Base.metadata.create_all(bind=engine)
