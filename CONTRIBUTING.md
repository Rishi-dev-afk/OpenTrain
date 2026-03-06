# Contributing to OpenTrain

Thanks for your interest in contributing. OpenTrain is intentionally designed to be easy to extend — the most common contribution (adding a new workload type) takes about 10 lines of code.

---

## Ways to Contribute

- **New workload types** — the most impactful and lowest-friction contribution
- **Coordinator scheduling improvements** — swap FIFO for priority or capability-aware scheduling
- **Dashboard improvements** — charts, export formats, dark/light toggle
- **Integration tests** — end-to-end job lifecycle coverage
- **Documentation** — architecture diagrams, guides, translations
- **Bug reports** — open a GitHub issue with reproduction steps

---

## Adding a New Workload Type

This is the most common contribution. Everything is isolated in `worker/ml_tasks.py`.

### Step 1 — Write the function

```python
# worker/ml_tasks.py

def run_my_workload(payload: dict) -> dict:
    """
    Input payload:
        {"data": ["item1", "item2", ...], "config": {"job_type": "my_workload"}}

    Output:
        {"output": [...]}   # one result per input item
    """
    texts = payload.get("data", [])
    results = [do_something(t) for t in texts]
    return {"output": results}
```

### Step 2 — Register it

```python
# worker/ml_tasks.py — TASK_REGISTRY

TASK_REGISTRY = {
    "embedding":    run_embedding,
    "tokenize":     run_tokenize,
    "preprocess":   run_preprocess,
    "my_workload":  run_my_workload,   # ← add this line
}
```

### Step 3 — Handle the merge in the coordinator

```python
# coordinator/aggregator.py — _merge_results()

elif job_type == "my_workload":
    items = data.get("output", [])   # match your output key
```

### Step 4 — Add to the dashboard job type list

```typescript
// web-dashboard/pages/submit.tsx — JOB_TYPES

{ value: 'my_workload', label: 'My Workload', desc: 'What it does' },
```

That's it. Open a PR with those four changes plus a brief description of what the workload does.

---

## Development Setup

```bash
# Clone
git clone https://github.com/your-org/opentrain
cd opentrain

# Coordinator
cd coordinator
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Worker (separate terminal)
cd worker
pip install -r requirements.txt
python worker.py --server http://localhost:8000

# Dashboard (separate terminal)
cd web-dashboard
npm install && npm run dev
```

---

## Pull Request Guidelines

- Keep PRs focused — one feature or fix per PR
- Add a brief description of what changed and why
- If adding a workload type, include an example input/output in the PR description
- New workload types don't require tests for the MVP; integration tests are a bonus

---

## Reporting Bugs

Open a GitHub issue with:
1. What you were doing
2. What you expected to happen
3. What actually happened
4. Coordinator logs (from `docker compose logs coordinator`)