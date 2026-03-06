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
import re
from typing import Any

# Lazy imports — models are loaded once on first use and cached as module globals
_embedding_model = None
_sentiment_model = None
_zero_shot_model = None


# ─── Helper: Extract text from payload data ────────────────────────────────────

def _extract_texts(data: list) -> list[str]:
    """
    Convert payload data to a list of strings.
    Handles both List[str] and List[dict] formats.
    
    For dicts, tries to extract text from known fields:
    "text" → "content" → "message" → first string field → stringify
    """
    if not data:
        return []
    
    result = []
    for item in data:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict):
            # Priority: "text" field → "content" → "message" → first string field
            text = None
            for key in ["text", "content", "message", "input", "data", "value"]:
                if key in item and isinstance(item[key], str):
                    text = item[key]
                    break
            # Fall back to first string-valued field
            if text is None:
                for value in item.values():
                    if isinstance(value, str):
                        text = value
                        break
            # Last resort: stringify
            if text is None:
                text = json.dumps(item) if item else ""
            result.append(text)
        else:
            result.append(str(item))
    
    return result


# ─── Embedding ────────────────────────────────────────────────────────────────

def run_embedding(payload: dict) -> dict:
    """
    Generate sentence embeddings for a list of text strings.

    Input payload:
        {"data": ["text 1", "text 2", ...], "config": {"job_type": "embedding", "model": "small"}}
        OR
        {"data": [{"text": "...", ...}, {"text": "...", ...}], "config": {...}}

    Output:
        {"embeddings": [[0.1, 0.2, ...], ...]}   # one vector per input text
    """
    global _embedding_model

    texts = _extract_texts(payload.get("data", []))
    if not texts:
        return {"embeddings": []}

    if _embedding_model is None:
        print("[ml_tasks] Loading sentence-transformers model (first call)...")
        from sentence_transformers import SentenceTransformer
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
        print("[ml_tasks] Model loaded.")

    embeddings = _embedding_model.encode(texts, show_progress_bar=False)
    return {"embeddings": embeddings.tolist()}


# ─── Sentiment Analysis ────────────────────────────────────────────────────────

def run_sentiment(payload: dict) -> dict:
    """
    Classify text sentiment as positive/negative/neutral.

    Input payload:
        {"data": ["This is great!", "I hate this.", ...], "config": {"job_type": "sentiment"}}
        OR
        {"data": [{"text": "...", ...}, {"text": "...", ...}], "config": {...}}

    Output:
        {"sentiments": [{"text": "...", "label": "positive", "score": 0.95}, ...]}
    """
    global _sentiment_model

    texts = _extract_texts(payload.get("data", []))
    if not texts:
        return {"sentiments": []}

    if _sentiment_model is None:
        print("[ml_tasks] Loading sentiment model...")
        from transformers import pipeline
        _sentiment_model = pipeline("sentiment-analysis", model="distilbert-base-uncased-finetuned-sst-2-english")
        print("[ml_tasks] Sentiment model loaded.")

    results = []
    for text in texts:
        try:
            output = _sentiment_model(text[:512])[0]  # limit to 512 tokens
            results.append({
                "text": text,
                "label": output["label"].lower(),
                "score": round(output["score"], 4)
            })
        except Exception as e:
            results.append({"text": text, "label": "error", "score": 0.0, "error": str(e)})

    return {"sentiments": results}


# ─── Statistical Analysis ─────────────────────────────────────────────────────

def run_stats(payload: dict) -> dict:
    """
    Compute statistical analysis of text data.

    Input payload:
        {"data": ["text 1", "text 2", ...], "config": {"job_type": "stats"}}
        OR
        {"data": [{"text": "...", ...}, ...], "config": {...}}

    Output:
        {
            "stats": {
                "total_texts": 100,
                "avg_length": 45.2,
                "avg_words": 8.5,
                "min_length": 5,
                "max_length": 234,
                "unique_words": 1250,
                "vocabulary_richness": 0.45,
                "top_words": [["word", 25], ...],
                "top_bigrams": [["word word", 8], ...],
                "sentence_count": 156
            }
        }
    """
    data = payload.get("data", [])
    texts = []
    for item in data:
        if isinstance(item, str):
            texts.append(item)
        elif isinstance(item, dict):
            # For structured data (e.g., CSV rows), concatenate all string values
            text_parts = [str(v) for v in item.values() if isinstance(v, str)]
            texts.append(' '.join(text_parts))
        else:
            texts.append(str(item))
    
    if not texts:
        return {"stats": {}}

    # Basic statistics
    total_texts = len(texts)
    lengths = [len(t) for t in texts]
    word_counts = [len(t.split()) for t in texts]

    # Word-level analysis
    all_words = []
    all_bigrams = []
    unique_words_set = set()

    for text in texts:
        # Tokenize and lowercase
        words = re.findall(r'\b\w+\b', text.lower())
        all_words.extend(words)
        unique_words_set.update(words)

        # Bigrams
        for i in range(len(words) - 1):
            all_bigrams.append(f"{words[i]} {words[i+1]}")

    # Count frequencies
    from collections import Counter
    word_freq = Counter(all_words)
    bigram_freq = Counter(all_bigrams)

    # Sentence count (rough estimate)
    sentence_count = sum(len(re.split(r'[.!?]+', t)) - 1 for t in texts)

    stats_result = {
        "total_texts": total_texts,
        "avg_length": round(sum(lengths) / len(lengths), 2) if lengths else 0,
        "avg_words": round(sum(word_counts) / len(word_counts), 2) if word_counts else 0,
        "min_length": min(lengths) if lengths else 0,
        "max_length": max(lengths) if lengths else 0,
        "median_length": sorted(lengths)[len(lengths) // 2] if lengths else 0,
        "unique_words": len(unique_words_set),
        "total_words": len(all_words),
        "vocabulary_richness": round(len(unique_words_set) / len(all_words), 4) if all_words else 0,
        "avg_sentence_length": round(sum(word_counts) / max(sentence_count, 1), 2),
        "top_10_words": word_freq.most_common(10),
        "top_10_bigrams": bigram_freq.most_common(10),
    }

    return {"stats": stats_result}


# ─── Tokenize ─────────────────────────────────────────────────────────────────

def run_tokenize(payload: dict) -> dict:
    """
    Whitespace-tokenize a list of text strings.
    Simple MVP implementation — swap for a real tokenizer as needed.

    Input payload:
        {"data": ["hello world", ...], "config": {...}}
        OR
        {"data": [{"text": "...", ...}, ...], "config": {...}}

    Output:
        {"output": [["hello", "world"], ...]}
    """
    texts = _extract_texts(payload.get("data", []))
    tokenized = [text.split() for text in texts]
    return {"output": tokenized}


# ─── Preprocess ───────────────────────────────────────────────────────────────

def run_preprocess(payload: dict) -> dict:
    """
    Basic text preprocessing: lowercase + strip.
    Placeholder — extend with real cleaning logic as needed.

    Input payload:
        {"data": ["  Hello World  ", ...], "config": {...}}
        OR
        {"data": [{"text": "...", ...}, ...], "config": {...}}

    Output:
        {"output": ["hello world", ...]}
    """
    texts = _extract_texts(payload.get("data", []))
    cleaned = [text.strip().lower() for text in texts]
    return {"output": cleaned}


# ─── Registry ─────────────────────────────────────────────────────────────────

TASK_REGISTRY: dict[str, Any] = {
    "embedding":  run_embedding,
    "sentiment":  run_sentiment,
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