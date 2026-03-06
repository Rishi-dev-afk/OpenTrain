"""
ml_tasks.py — ML computation dispatch for OpenTrain workers.

Each function receives a parsed task payload dict and returns a result dict
that will be JSON-serialised and posted back to the coordinator.

Adding a new workload type:
  1. Write a function: def run_<type>(payload: dict) -> dict
  2. Register it in TASK_REGISTRY at the bottom of this file.
"""
from __future__ import annotations
import json
from typing import Any

# Lazy imports — models are loaded once on first use and cached as module globals
_embedding_model = None


# ─── Embedding ────────────────────────────────────────────────────────────────

def run_embedding(payload: dict) -> dict:
    """
    Generate sentence embeddings for a list of text strings.

    Input payload:
        {"data": ["text 1", "text 2", ...], "config": {"job_type": "embedding"}}

    Output:
        {"embeddings": [[0.1, 0.2, ...], ...]}   # one vector per input text
    """
    global _embedding_model

    texts = payload.get("data", [])
    if not texts:
        return {"embeddings": []}

    if _embedding_model is None:
        print("[ml_tasks] Loading sentence-transformers model (first call)...")
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[ml_tasks] Model loaded.")

    embeddings = _embedding_model.encode(texts, show_progress_bar=False)
    return {"embeddings": embeddings.tolist()}


# ─── Tokenize ─────────────────────────────────────────────────────────────────

def run_tokenize(payload: dict) -> dict:
    """
    Whitespace-tokenize a list of text strings.
    Simple MVP implementation — swap for a real tokenizer as needed.

    Input payload:
        {"data": ["hello world", ...], "config": {...}}

    Output:
        {"output": [["hello", "world"], ...]}
    """
    texts = payload.get("data", [])
    tokenized = [text.split() for text in texts]
    return {"output": tokenized}


# ─── Preprocess ───────────────────────────────────────────────────────────────

def run_preprocess(payload: dict) -> dict:
    """
    Basic text preprocessing: lowercase + strip.
    Placeholder — extend with real cleaning logic as needed.

    Input payload:
        {"data": ["  Hello World  ", ...], "config": {...}}

    Output:
        {"output": ["hello world", ...]}
    """
    texts = payload.get("data", [])
    cleaned = [text.strip().lower() for text in texts]
    return {"output": cleaned}


# ─── Registry ─────────────────────────────────────────────────────────────────

TASK_REGISTRY: dict[str, Any] = {
    "embedding":  run_embedding,
    "tokenize":   run_tokenize,
    "preprocess": run_preprocess,
}


def dispatch(job_type: str, payload: dict) -> dict:
    """
    Dispatch a task to the correct ML function.
    Raises ValueError for unknown job types.
    """
    fn = TASK_REGISTRY.get(job_type)
    if fn is None:
        raise ValueError(
            f"Unknown job_type '{job_type}'. "
            f"Supported types: {list(TASK_REGISTRY.keys())}"
        )
    return fn(payload)