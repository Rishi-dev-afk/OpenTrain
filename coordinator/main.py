"""
OpenTrain Coordinator — FastAPI entrypoint.

Deployment notes (Render):
  - $PORT is injected by Render at runtime; uvicorn reads it via the start command.
  - $ALLOWED_ORIGINS is a comma-separated list of allowed CORS origins.
    Set this to your Vercel dashboard URL in the Render environment variables.
  - SQLite DB and result artifacts are written to /app/data (mounted Render disk).
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from models import create_tables
from routes import jobs, tasks, workers
from scheduler import build_scheduler

# ─── CORS ─────────────────────────────────────────────────────────────────────

def _parse_origins() -> list[str]:
    raw = os.environ.get("ALLOWED_ORIGINS", "*")
    if raw == "*":
        return ["*"]
    return [o.strip() for o in raw.split(",") if o.strip()]

ALLOWED_ORIGINS = _parse_origins()

# ─── App lifecycle ────────────────────────────────────────────────────────────

_scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler
    create_tables()
    _scheduler = build_scheduler()
    _scheduler.start()
    print("[opentrain] Coordinator started. Background scheduler running.")
    yield
    _scheduler.shutdown()
    print("[opentrain] Coordinator shut down.")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OpenTrain Coordinator",
    description="Distributed ML compute coordinator — schedules tasks across volunteer worker nodes.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jobs.router)
app.include_router(tasks.router)
app.include_router(workers.router)


@app.get("/", tags=["health"])
def root():
    return {
        "service": "OpenTrain Coordinator",
        "status": "ok",
        "version": "0.1.0",
    }


@app.get("/health", tags=["health"])
def health_check():
    """Render uses this endpoint for health checks."""
    return {"status": "ok"}
