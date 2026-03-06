# OpenTrain

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

**OpenTrain turns volunteer machines into a distributed ML compute network.**

Running large ML workloads is expensive and centralized. Cloud compute costs money, powerful single machines are scarce, and existing distributed systems like Ray or Spark are too complex for most people to self-host. Meanwhile, there are millions of idle laptops, desktops, and servers sitting unused — volunteer compute that has nowhere to go.

OpenTrain fixes this. It splits ML workloads — embedding generation, tokenization, dataset preprocessing — into small shards and distributes them across any machines that opt in. Volunteers contribute compute with a single command. Jobs complete faster the more workers join. Results are merged and returned to the user as a single downloadable artifact.

The core idea: **shardable ML tasks + volunteer machines + a coordinator = distributed ML compute for everyone.**

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Supported Workloads](#supported-workloads)
- [Quick Start](#quick-start)
- [Deployment](#deployment)
- [Local Development](#local-development)
- [API Documentation](#api-documentation)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

OpenTrain has three components that work together:

- **Coordinator** — the brain. Accepts jobs, shards datasets into tasks, maintains a queue, assigns work to volunteers, collects results, and merges them into a final artifact.
- **Workers** — the muscle. Lightweight Python processes that run on volunteer machines. They register with the coordinator, poll for tasks, execute ML locally, and return results. Stateless and disposable — workers can join or leave at any time without breaking anything.
- **Dashboard** — the interface. A web UI for submitting jobs, watching live progress across workers, and downloading completed results.

The system is built around a **pull model**: workers request tasks from the coordinator rather than having tasks pushed to them. This means no NAT or firewall issues for volunteers, natural handling of worker churn, and graceful degradation if machines disappear mid-job.

---

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Dashboard │────│   Coordinator    │◄───│   Worker Nodes  │
│    (Next.js)    │    │   (FastAPI)      │    │  (Python)       │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   SQLite DB      │
                       │   + Results      │
                       └──────────────────┘
```

**Job lifecycle:**

```
User submits dataset
        │
        ▼
Coordinator shards it into N tasks
        │
        ▼
Workers pull tasks, run ML locally, return results
        │
        ▼
Coordinator aggregates → single downloadable artifact
```

The more workers that join, the faster jobs complete. Workers are completely stateless — all context is included in the task payload, so machines can process tasks without knowing anything about the broader job.

---

## Features

### Reliability & Fault Tolerance

Volunteer networks are inherently unreliable. OpenTrain is built around this reality:

- **Heartbeat monitor** — workers that miss 60 seconds of heartbeats are marked offline; their in-flight tasks are immediately returned to the queue for reassignment
- **Task timeout** — tasks assigned but not completed within 5 minutes are automatically requeued, even if the worker is still alive but hung
- **Retry limit** — tasks that fail 3 times are marked permanently failed; the parent job is flagged
- **Stalled job recovery** — a background pass re-derives task counts from the database to catch drift and trigger aggregation if a job silently completed
- **Atomic artifact writes** — results are written to a temp file then renamed into place so the download endpoint never sees a partial file
- **Checksum verification** — workers include a SHA-256 of their result payload; mismatches are rejected and the task is requeued

### Scalability

- Task sharding allows arbitrarily large datasets to be processed in parallel
- Workers are stateless and horizontally scalable — spin up as many as you have machines for
- The coordinator is lightweight and runs on a small free-tier VM

### Developer Experience

- Adding a new workload type takes ~10 lines of Python — see [CONTRIBUTING.md](CONTRIBUTING.md)
- Interactive API docs auto-generated at `/docs` (Swagger UI)
- TypeScript types flow from the coordinator API schema through to the dashboard
- Full local dev stack via Docker Compose

---

## Supported Workloads

| Job Type     | Description | Output | Use Case |
|--------------|-------------|--------|----------|
| `embedding`  | Sentence embeddings via `all-MiniLM-L6-v2` | 384-d float vectors | Semantic search, clustering |
| `tokenize`   | Whitespace tokenization | token arrays | Text preprocessing |
| `preprocess` | Lowercase + trim | cleaned lines | Normalization |
| `sentiment`  | Sentiment classification via DistilBERT | `{label, score}` | Opinion mining |

Adding a new workload:

1. Add `run_<name>` to `worker/ml_tasks.py`
2. Register it in `TASK_REGISTRY`
3. Update `_merge_results` in `coordinator/aggregator.py` if needed
4. Add the option to `web-dashboard/pages/submit.tsx`

See [CONTRIBUTING.md](CONTRIBUTING.md) for a full walkthrough.

---

## Quick Start
### Try it in 60 seconds (no Docker)

The coordinator and dashboard are already deployed. Run a worker locally and point it at the live system:
```bash
git clone https://github.com/Rishi-dev-afk/OpenTrain.git

cd OpenTrain

pip install -r worker/requirements.txt # Skip ONLY if necessary requirements already satisfied.

python worker/worker.py --server https://opentrain.onrender.com

https://open-train.vercel.app #Public deployed Dashboard
```
Note: The requirements may appear bulky, but are standard ML libraries needed for distributed task execution.

## Launch the Full Stack Locally
### Prerequisites

- Docker & docker-compose
- Git

```bash
git clone https://github.com/Rishi-dev-afk/OpenTrain.git
cd OpenTrain
docker compose up --build
```

| Service     | URL                        |
|-------------|----------------------------|
| Dashboard   | http://localhost:3000       |
| Coordinator | http://localhost:8000       |
| API Docs    | http://localhost:8000/docs  |


---

## Deployment

| Service     | Platform | URL                              |
|-------------|----------|----------------------------------|
| Coordinator | Render   | https://opentrain.onrender.com   |
| Dashboard   | Vercel   | https://open-train.vercel.app    |

### Deploy your own

**Coordinator on Render:**
1. Fork the repo
2. New Render service → connect repo → set root directory to `coordinator/`
3. Build command: `pip install -r requirements.txt`
4. Start command: `bash start.sh`
5. Add environment variable `ALLOWED_ORIGINS` pointing to your dashboard URL

**Dashboard on Vercel:**
1. New Vercel project → connect repo → set root directory to `web-dashboard/`
2. Add environment variable `NEXT_PUBLIC_COORDINATOR_URL=https://your-coordinator.onrender.com`
3. Deploy

**Workers — run anywhere:**
```bash
python worker/worker.py --server https://your-coordinator.onrender.com
```
Any machine with Python and network access can contribute compute.

---

## Local Development

**Coordinator:**
```bash
cd coordinator
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

**Worker:**
```bash
cd worker
pip install -r requirements.txt
python worker.py --server http://localhost:8000
```

**Dashboard:**
```bash
cd web-dashboard
cp .env.local.example .env.local
npm install
npm run dev
# → http://localhost:3000
```

---

## Project Structure

```
opentrain/
├── coordinator/          FastAPI coordinator server
│   ├── main.py           App entrypoint + lifecycle
│   ├── models.py         SQLAlchemy models (Job, Task, Worker)
│   ├── schemas.py        Pydantic request/response schemas
│   ├── aggregator.py     Result merging + atomic artifact write
│   ├── scheduler.py      Background jobs (heartbeat, timeout, recovery)
│   ├── routes/
│   │   ├── jobs.py       /jobs endpoints
│   │   ├── tasks.py      /tasks/next + result submission
│   │   └── workers.py    /workers/register + heartbeat
│   └── start.sh          Production startup script
│
├── worker/               Volunteer worker node
│   ├── worker.py         Poll loop + heartbeat thread
│   └── ml_tasks.py       ML dispatch (embedding, tokenize, preprocess, etc.)
│
├── web-dashboard/        Next.js control plane
│   ├── pages/
│   │   ├── index.tsx     Job queue list (live polling)
│   │   ├── submit.tsx    Job submission form
│   │   ├── workers.tsx   Worker nodes dashboard
│   │   └── jobs/[id].tsx Job detail + per-task breakdown
│   ├── lib/
│   │   └── api.ts        Typed coordinator API client
│   └── vercel.json
│
├── docs/
│   ├── architecture.md
│   └── api-reference.md
│
├── docker-compose.yml
├── render.yaml
├── CONTRIBUTING.md
├── ROADMAP.md
└── README.md
```

---

## API Documentation

| Method | Endpoint                    | Description                     |
|--------|-----------------------------|---------------------------------|
| POST   | `/jobs/`                    | Submit a new job                |
| GET    | `/jobs/`                    | List all jobs                   |
| GET    | `/jobs/{id}`                | Job detail + task breakdown     |
| GET    | `/jobs/{id}/result`         | Download merged result artifact |
| POST   | `/tasks/{id}/complete`      | Worker submits result           |
| POST   | `/workers/ping`             | Worker heartbeat                |
| GET    | `/workers`                  | List registered workers         |

Full interactive docs at `/docs` (Swagger UI) and `/redoc`.

---

## Contributing

OpenTrain is designed to be easy to extend. The most common contribution — adding a new workload type — takes about 10 lines of code and is fully documented in [CONTRIBUTING.md](CONTRIBUTING.md).

Other ways to contribute:
- New workload types (highest impact, lowest friction)
- Coordinator scheduling improvements
- Dashboard UI enhancements
- Integration tests
- Documentation

---

## Roadmap

Near-term: GPU scheduling, worker reputation system, dataset connectors (HuggingFace Hub, S3), token-based authentication.

Long-term: distributed model training, multi-coordinator federation, decentralized coordination, incentive layer for volunteer compute.

See [ROADMAP.md](ROADMAP.md) for the full plan.

---

## License

MIT © [Rishi-dev-afk](https://github.com/Rishi-dev-afk)
