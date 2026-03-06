"""
scheduler.py — Background reliability layer for the OpenTrain coordinator.

Three periodic jobs run every SCHEDULER_INTERVAL_SECONDS:

  1. check_heartbeats()
       Marks workers offline when their heartbeat goes stale.
       Reassigns (or fails) every in-flight task they owned.

  2. check_task_timeouts()
       Catches tasks that are still "assigned" but whose worker never
       reported back within TASK_TIMEOUT_MINUTES — even if the worker
       itself is still sending heartbeats (e.g. worker is alive but hung
       on one task forever).

  3. check_stalled_jobs()
       Catches jobs that are stuck in "in_progress" with zero pending or
       assigned tasks remaining — can happen if a race condition leaves
       done_tasks out of sync. Re-derives done_tasks from the DB and
       triggers aggregation if everything is actually complete.

All three functions open their own DB session so they are safe to call
from a background thread independent of the FastAPI request lifecycle.
"""

from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler

from aggregator import try_aggregate_job
from models import Job, Task, Worker, SessionLocal

# ─── Tunables ─────────────────────────────────────────────────────────────────

HEARTBEAT_TIMEOUT_SECONDS  = 60    # worker declared offline after this
TASK_TIMEOUT_MINUTES       = 5     # assigned task timed out after this
MAX_TASK_ATTEMPTS          = 3     # give up on a task after this many tries
SCHEDULER_INTERVAL_SECONDS = 30    # how often each job fires


# ─── Job 1: Heartbeat monitor ─────────────────────────────────────────────────

def check_heartbeats():
    """
    Scan for workers whose last_heartbeat is older than HEARTBEAT_TIMEOUT_SECONDS.

    For each stale worker:
      - Mark the worker offline
      - For every task it owns in status=assigned:
          * If attempts < MAX_TASK_ATTEMPTS → return to pending queue
          * If attempts >= MAX_TASK_ATTEMPTS → mark failed, fail the parent job
    """
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(seconds=HEARTBEAT_TIMEOUT_SECONDS)
        stale_workers = (
            db.query(Worker)
            .filter(Worker.status != "offline", Worker.last_heartbeat < cutoff)
            .all()
        )

        if not stale_workers:
            return

        for worker in stale_workers:
            print(f"[scheduler] Worker {worker.id[:8]}… offline (last heartbeat: {worker.last_heartbeat})")
            worker.status = "offline"

            stuck_tasks = (
                db.query(Task)
                .filter(Task.worker_id == worker.id, Task.status == "assigned")
                .all()
            )

            for task in stuck_tasks:
                _handle_failed_task(task, db, reason="worker went offline")

        db.commit()

    except Exception as e:
        print(f"[scheduler] ERROR in check_heartbeats: {e}")
        db.rollback()
    finally:
        db.close()


# ─── Job 2: Task timeout ──────────────────────────────────────────────────────

def check_task_timeouts():
    """
    Scan for tasks that are still assigned but have exceeded TASK_TIMEOUT_MINUTES.

    This catches workers that are alive (heartbeat OK) but silently hung on a
    single task — e.g. an OOM, an infinite loop in user code, etc.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(minutes=TASK_TIMEOUT_MINUTES)
        timed_out = (
            db.query(Task)
            .filter(Task.status == "assigned", Task.assigned_at < cutoff)
            .all()
        )

        if not timed_out:
            return

        for task in timed_out:
            elapsed = (datetime.utcnow() - task.assigned_at).total_seconds() / 60
            print(
                f"[scheduler] Task {task.id[:8]}… timed out "
                f"({elapsed:.1f}m > {TASK_TIMEOUT_MINUTES}m limit, "
                f"attempt {task.attempts}/{MAX_TASK_ATTEMPTS})"
            )
            _handle_failed_task(task, db, reason="task timeout")

        db.commit()

    except Exception as e:
        print(f"[scheduler] ERROR in check_task_timeouts: {e}")
        db.rollback()
    finally:
        db.close()


# ─── Job 3: Stalled job recovery ─────────────────────────────────────────────

def check_stalled_jobs():
    """
    Catch jobs stuck in "in_progress" with no pending or assigned tasks left.

    This can happen when done_tasks gets out of sync due to a race — e.g. two
    workers both claim the last task and one result is deduplicated, leaving
    done_tasks one short of total_tasks.

    Fix: re-derive done_tasks from the DB and trigger aggregation if warranted.
    """
    db = SessionLocal()
    try:
        active_jobs = (
            db.query(Job)
            .filter(Job.status == "in_progress")
            .all()
        )

        for job in active_jobs:
            tasks = db.query(Task).filter(Task.job_id == job.id).all()
            if not tasks:
                continue

            actual_done    = sum(1 for t in tasks if t.status == "completed")
            has_pending    = any(t.status in ("pending", "assigned") for t in tasks)
            has_failed     = any(t.status == "failed" for t in tasks)

            # Re-sync done_tasks in case it drifted
            if job.done_tasks != actual_done:
                print(
                    f"[scheduler] Job {job.id[:8]}… done_tasks drift: "
                    f"recorded={job.done_tasks}, actual={actual_done}. Correcting."
                )
                job.done_tasks = actual_done
                db.commit()

            # Job has a failed task → mark job failed
            if has_failed and not has_pending:
                print(f"[scheduler] Job {job.id[:8]}… has failed tasks and nothing pending — marking failed.")
                job.status = "failed"
                db.commit()
                continue

            # All tasks complete but job not yet aggregated → trigger aggregation
            if not has_pending and actual_done == job.total_tasks:
                print(f"[scheduler] Job {job.id[:8]}… all tasks done but not aggregated — triggering.")
                try_aggregate_job(job.id, db)

    except Exception as e:
        print(f"[scheduler] ERROR in check_stalled_jobs: {e}")
        db.rollback()
    finally:
        db.close()


# ─── Shared helper ────────────────────────────────────────────────────────────

def _handle_failed_task(task: Task, db, reason: str):
    """
    Decide whether to requeue a task or permanently fail it (and its job).
    Does NOT commit — caller is responsible for db.commit().
    """
    if task.attempts >= MAX_TASK_ATTEMPTS:
        task.status = "failed"
        job = db.query(Job).filter(Job.id == task.job_id).first()
        if job and job.status != "failed":
            job.status = "failed"
            print(
                f"[scheduler] Task {task.id[:8]}… permanently failed "
                f"({reason}, {task.attempts} attempts). Job {job.id[:8]}… → failed."
            )
    else:
        task.status     = "pending"
        task.worker_id  = None
        task.assigned_at = None
        print(
            f"[scheduler] Task {task.id[:8]}… requeued "
            f"({reason}, attempt {task.attempts}/{MAX_TASK_ATTEMPTS})."
        )


# ─── Scheduler setup ─────────────────────────────────────────────────────────

def build_scheduler() -> BackgroundScheduler:
    """
    Create and configure the APScheduler instance.
    Call .start() in the FastAPI lifespan and .shutdown() on teardown.
    """
    sched = BackgroundScheduler(timezone="UTC")

    sched.add_job(
        check_heartbeats,
        "interval",
        seconds=SCHEDULER_INTERVAL_SECONDS,
        id="heartbeats",
        max_instances=1,        # don't pile up if a run takes longer than interval
        misfire_grace_time=10,
    )
    sched.add_job(
        check_task_timeouts,
        "interval",
        seconds=SCHEDULER_INTERVAL_SECONDS,
        id="task_timeouts",
        max_instances=1,
        misfire_grace_time=10,
    )
    sched.add_job(
        check_stalled_jobs,
        "interval",
        seconds=SCHEDULER_INTERVAL_SECONDS * 2,  # less urgent, run half as often
        id="stalled_jobs",
        max_instances=1,
        misfire_grace_time=30,
    )

    return sched