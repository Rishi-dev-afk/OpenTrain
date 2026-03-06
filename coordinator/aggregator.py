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
from collections import Counter

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

def _merge_results(job_type: str, tasks: list) -> tuple[dict | list, dict]:
    """
    Merge task results based on job type.
    Returns (merged_result, stats_dict).
    """
    if job_type == "stats":
        return _merge_stats(tasks)
    elif job_type == "sentiment":
        return _merge_sentiment(tasks)
    else:
        return _merge_standard(job_type, tasks)


def _merge_standard(job_type: str, tasks: list) -> tuple[list, dict]:
    """Standard merge: concatenate output arrays."""
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


def _merge_sentiment(tasks: list) -> tuple[list, dict]:
    """Merge sentiment results with aggregated statistics."""
    merged = []
    positive_count = 0
    negative_count = 0
    neutral_count = 0
    scores = []

    for task in tasks:
        if not task.result:
            continue
        data = json.loads(task.result)
        sentiments = data.get("sentiments", [])

        for sentiment in sentiments:
            merged.append(sentiment)
            label = sentiment.get("label", "").lower()
            score = sentiment.get("score", 0)

            if label == "positive":
                positive_count += 1
            elif label == "negative":
                negative_count += 1
            else:
                neutral_count += 1

            if label != "error":
                scores.append(score)

    # Create aggregated result
    total = len(merged)
    avg_score = sum(scores) / len(scores) if scores else 0

    return {
        "results": merged,
        "summary": {
            "total_documents": total,
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
            "avg_confidence": round(avg_score, 4),
            "positive_pct": round((positive_count / total * 100), 2) if total > 0 else 0,
            "negative_pct": round((negative_count / total * 100), 2) if total > 0 else 0,
            "neutral_pct": round((neutral_count / total * 100), 2) if total > 0 else 0,
        }
    }, {"total_items": total}


def _merge_stats(tasks: list) -> tuple[dict, dict]:
    """Merge statistical analysis results across shards."""
    all_stats = []

    for task in tasks:
        if not task.result:
            continue
        data = json.loads(task.result)
        stats = data.get("stats", {})
        if stats:
            all_stats.append(stats)

    if not all_stats:
        return {"error": "No statistics to merge"}, {"total_items": 0}

    # Aggregate statistics across all shards
    merged_stats = {
        "total_texts": sum(s.get("total_texts", 0) for s in all_stats),
        "total_words": sum(s.get("total_words", 0) for s in all_stats),
        "unique_words": len(set(word for s in all_stats for word, _ in s.get("top_10_words", []))),
        "avg_document_length": round(
            sum(s.get("total_texts", 0) * s.get("avg_length", 0) for s in all_stats) / 
            max(sum(s.get("total_texts", 0) for s in all_stats), 1),
            2
        ),
        "avg_words_per_document": round(
            sum(s.get("total_texts", 0) * s.get("avg_words", 0) for s in all_stats) / 
            max(sum(s.get("total_texts", 0) for s in all_stats), 1),
            2
        ),
        "overall_vocabulary_richness": round(
            len(set(word for s in all_stats for word, _ in s.get("top_10_words", []))) /
            max(sum(s.get("total_words", 0) for s in all_stats), 1),
            4
        ),
        "min_length": min(s.get("min_length", float('inf')) for s in all_stats) if all_stats else 0,
        "max_length": max(s.get("max_length", 0) for s in all_stats) if all_stats else 0,
    }

    # Aggregate top words and bigrams
    from collections import Counter
    word_counts = Counter()
    bigram_counts = Counter()

    for s in all_stats:
        if isinstance(s.get("top_10_words"), list):
            for word, count in s.get("top_10_words", []):
                word_counts[word] += count
        if isinstance(s.get("top_10_bigrams"), list):
            for bigram, count in s.get("top_10_bigrams", []):
                bigram_counts[bigram] += count

    merged_stats["top_20_words"] = word_counts.most_common(20)
    merged_stats["top_20_bigrams"] = bigram_counts.most_common(20)

    return {"stats": merged_stats}, {"total_items": sum(s.get("total_texts", 0) for s in all_stats)}


# ─── Artifact helpers ─────────────────────────────────────────────────────────

def artifact_path(job_id: str) -> str:
    return os.path.join(RESULTS_DIR, f"{job_id}.json")


def artifact_exists(job_id: str) -> bool:
    return os.path.exists(artifact_path(job_id))
