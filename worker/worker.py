"""
worker.py — OpenTrain volunteer worker client.

Usage:
    python worker.py --server http://localhost:8000 --token <join_token>

Or via Docker:
    docker run opentrain/worker --server http://<url> --token <token>

The worker:
  1. Registers with the coordinator → receives worker_id
  2. Starts a background heartbeat thread (every 30s)
  3. Polls for tasks in a tight loop
  4. Runs ML computation locally via ml_tasks.dispatch()
  5. Posts result (or failure) back to coordinator
  6. Repeats until interrupted
"""
from __future__ import annotations

import argparse
import hashlib
import json
import socket
import sys
import time
import threading
from typing import Optional

import requests

from ml_tasks import dispatch

# ─── Configuration ────────────────────────────────────────────────────────────

POLL_INTERVAL_SECONDS      = 2     # how long to wait when no tasks are available
HEARTBEAT_INTERVAL_SECONDS = 30    # how often to ping the coordinator
REQUEST_TIMEOUT_SECONDS    = 15    # HTTP timeout for API calls
MAX_NETWORK_RETRIES        = 3     # retries on transient network errors
RETRY_BACKOFF_SECONDS      = 5     # wait between retries


# ─── HTTP helpers ─────────────────────────────────────────────────────────────

def _post(url: str, data: dict, retries: int = MAX_NETWORK_RETRIES) -> Optional[dict]:
    """POST with retry + exponential-ish backoff. Returns parsed JSON or None."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.post(url, json=data, timeout=REQUEST_TIMEOUT_SECONDS)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.RequestException as e:
            print(f"[worker] POST {url} failed (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    return None


def _get(url: str, params: dict = None, retries: int = MAX_NETWORK_RETRIES) -> Optional[dict]:
    """GET with retry. Returns parsed JSON or None."""
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(url, params=params, timeout=REQUEST_TIMEOUT_SECONDS)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 404:
                return None   # no task available — not an error
            resp.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"[worker] GET {url} failed (attempt {attempt}/{retries}): {e}")
            if attempt < retries:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    return None


# ─── Registration ─────────────────────────────────────────────────────────────

def register(server: str) -> str:
    """Register with coordinator and return worker_id."""
    hostname = socket.gethostname()
    print(f"[worker] Registering with coordinator at {server} (hostname: {hostname})...")

    result = _post(f"{server}/workers/register", {"hostname": hostname})
    if not result or "worker_id" not in result:
        print("[worker] Registration failed. Exiting.")
        sys.exit(1)

    worker_id = result["worker_id"]
    print(f"[worker] Registered. worker_id = {worker_id}")
    return worker_id


# ─── Heartbeat ────────────────────────────────────────────────────────────────

def heartbeat_loop(server: str, worker_id: str, stop_event: threading.Event):
    """Background thread: send heartbeat to coordinator every 30 seconds."""
    while not stop_event.is_set():
        resp = _post(f"{server}/workers/heartbeat", {"worker_id": worker_id})
        if resp:
            print(f"[worker] ♥ heartbeat sent")
        else:
            print(f"[worker] ⚠ heartbeat failed — coordinator may be unreachable")
        stop_event.wait(HEARTBEAT_INTERVAL_SECONDS)


# ─── Task execution ───────────────────────────────────────────────────────────

def _result_checksum(result: dict) -> str:
    """SHA-256 of the JSON-serialised result (sorted keys for determinism)."""
    raw = json.dumps(result, sort_keys=True).encode()
    return hashlib.sha256(raw).hexdigest()


def process_task(server: str, worker_id: str, task: dict) -> bool:
    """
    Execute one task and post the result.
    Returns True on success, False on failure.
    """
    task_id    = task["task_id"]
    job_type   = task["job_type"]
    task_index = task["task_index"]
    payload    = json.loads(task["payload"])

    print(f"[worker] → Task {task_index} ({task_id[:8]}…) | job_type={job_type} | {len(payload.get('data', []))} items")

    try:
        t_start = time.time()
        result  = dispatch(job_type, payload)
        elapsed = time.time() - t_start
        print(f"[worker] ✓ Task {task_index} done in {elapsed:.2f}s")
    except Exception as e:
        print(f"[worker] ✗ Task {task_index} failed: {e}")
        _post(
            f"{server}/tasks/{task_id}/fail",
            {"worker_id": worker_id, "error": str(e)},
        )
        return False

    # Serialise and checksum the result
    result_json = json.dumps(result)
    checksum    = _result_checksum(result)

    resp = _post(
        f"{server}/tasks/{task_id}/result",
        {"worker_id": worker_id, "result": result_json, "checksum": checksum},
    )

    if resp:
        print(f"[worker] ✓ Result submitted | {resp.get('job_progress', '?')}")
        return True
    else:
        print(f"[worker] ✗ Failed to submit result for task {task_id[:8]}…")
        return False


# ─── Main poll loop ───────────────────────────────────────────────────────────

def poll_loop(server: str, worker_id: str, stop_event: threading.Event):
    """Main loop: continuously pull tasks and process them."""
    print(f"[worker] Starting poll loop. Polling every {POLL_INTERVAL_SECONDS}s when idle...")

    while not stop_event.is_set():
        task = _get(f"{server}/tasks/next", params={"worker_id": worker_id})

        if task is None:
            # No tasks available — idle wait
            stop_event.wait(POLL_INTERVAL_SECONDS)
            continue

        process_task(server, worker_id, task)
        # No sleep after a successful task — immediately poll for the next one


# ─── Entrypoint ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="OpenTrain volunteer worker node")
    parser.add_argument("--server", required=True, help="Coordinator URL, e.g. http://localhost:8000")
    parser.add_argument("--token",  required=False, default=None, help="Join token (reserved for auth, unused in MVP)")
    args = parser.parse_args()

    server = args.server.rstrip("/")

    # 1. Register
    worker_id = register(server)

    # 2. Start heartbeat thread
    stop_event = threading.Event()
    hb_thread = threading.Thread(
        target=heartbeat_loop,
        args=(server, worker_id, stop_event),
        daemon=True,
        name="heartbeat",
    )
    hb_thread.start()

    # 3. Poll loop (blocks until KeyboardInterrupt)
    try:
        poll_loop(server, worker_id, stop_event)
    except KeyboardInterrupt:
        print("\n[worker] Shutting down...")
    finally:
        stop_event.set()
        hb_thread.join(timeout=5)
        print("[worker] Goodbye.")


if __name__ == "__main__":
    main()
