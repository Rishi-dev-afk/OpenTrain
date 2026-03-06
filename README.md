# OpenTrain

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

OpenTrain is a distributed machine learning compute coordinator that enables volunteers to contribute their computational resources for parallel ML processing tasks. Built for scalability and reliability, it allows users to submit datasets for processing across a network of volunteer worker nodes.

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

## Overview

OpenTrain solves the challenge of distributed ML computation by providing a robust coordination layer between job submitters and volunteer compute nodes. Users submit datasets through a web dashboard, which are automatically sharded into tasks and distributed to available workers. Workers process tasks locally using optimized ML libraries and return results for aggregation.

### Key Benefits

- **Distributed Processing**: Scale ML workloads across multiple volunteer machines
- **Fault Tolerance**: Automatic retry, timeout handling, and recovery mechanisms
- **Easy Deployment**: One-command setup for coordinators, dashboards, and workers
- **Extensible**: Simple framework for adding new ML workloads
- **Production Ready**: Built with FastAPI, Next.js, and comprehensive monitoring

## Architecture

OpenTrain consists of three main components:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Web Dashboard │────│   Coordinator    │◄───┤   Worker Nodes  │
│    (Next.js)    │    │   (FastAPI)      │    │  (Python/Docker) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌──────────────────┐
                       │   SQLite DB      │
                       │   + Results      │
                       └──────────────────┘
```

### Coordinator (`coordinator/`)

The central orchestration service built with FastAPI and SQLAlchemy:

- **Job Management**: Accepts job submissions, shards datasets into tasks
- **Task Scheduling**: FIFO task distribution to registered workers
- **Worker Monitoring**: Heartbeat tracking and automatic failover
- **Result Aggregation**: Merges task results into final artifacts
- **Background Scheduler**: Reliability layer with periodic health checks
- **API**: RESTful endpoints for all operations

**Database Schema:**
- `jobs`: Job metadata, status, progress tracking
- `tasks`: Individual work units with status and results
- `workers`: Registered compute nodes and their status

### Dashboard (`web-dashboard/`)

A modern React-based web interface built with Next.js:

- **Job Submission**: Intuitive forms for dataset upload and job configuration
- **Progress Monitoring**: Real-time job status and task-level details
- **Result Download**: Direct download of processed artifacts
- **Worker Overview**: Live view of connected volunteer nodes

### Workers (`worker/`)

Lightweight compute clients that volunteer processing power:

- **Registration**: Automatic registration with coordinator
- **Task Polling**: Continuous polling for available work
- **ML Execution**: Local processing using optimized libraries
- **Result Submission**: Integrity-verified result delivery
- **Fault Handling**: Automatic retry and failure reporting

## Features

### Reliability & Fault Tolerance

- **Heartbeat Monitoring**: Workers send periodic health signals
- **Task Timeouts**: Automatic reassignment of hung tasks
- **Retry Logic**: Configurable retry attempts with exponential backoff
- **Stalled Job Recovery**: Background detection and repair of stuck jobs
- **Result Integrity**: SHA-256 checksums for all task results

### Scalability

- **Horizontal Scaling**: Add unlimited worker nodes
- **Dataset Sharding**: Automatic splitting of large datasets
- **Load Balancing**: FIFO task distribution across workers
- **Resource Efficient**: Workers only download required ML models

### Developer Experience

- **Type Safety**: Full TypeScript support in dashboard
- **API Documentation**: Auto-generated OpenAPI/Swagger docs
- **Docker Support**: Containerized deployment everywhere
- **Local Development**: Complete stack with docker-compose
- **Extensible Framework**: Simple patterns for adding workloads

## Supported Workloads

OpenTrain ships with three built-in ML workloads:

### 1. Text Embedding (`embedding`)
- **Model**: `sentence-transformers/all-MiniLM-L6-v2`
- **Input**: Raw text lines
- **Output**: 384-dimensional sentence embeddings
- **Use Case**: Semantic search, clustering, similarity matching

### 2. Tokenization (`tokenize`)
- **Method**: Simple whitespace tokenization
- **Input**: Text lines
- **Output**: Token arrays per input line
- **Use Case**: Basic text preprocessing pipeline

### 3. Preprocessing (`preprocess`)
- **Operations**: Lowercase conversion + whitespace stripping
- **Input**: Raw text lines
- **Output**: Cleaned text lines
- **Use Case**: Text normalization for downstream ML tasks

### Adding New Workloads

Adding a new workload requires ~10 lines of code across 4 files:

1. **Implement the function** in `worker/ml_tasks.py`
2. **Register it** in the `TASK_REGISTRY`
3. **Handle aggregation** in `coordinator/aggregator.py`
4. **Add to dashboard** in `web-dashboard/pages/submit.tsx`

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed instructions.

## Quick Start

### Prerequisites

- Docker and docker-compose
- Git

### Run Everything Locally

```bash
# Clone the repository
git clone https://github.com/Rishi-dev-afk/OpenTrain.git
cd OpenTrain

# Start the complete stack
docker compose up --build

# Access the services:
# - Dashboard: http://localhost:3000
# - Coordinator API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
```

### Submit Your First Job

1. Open http://localhost:3000
2. Click "Submit Job"
3. Choose "Embedding Generation"
4. Paste some text (one sentence per line)
5. Click "Submit"
6. Watch progress in real-time
7. Download results when complete

## Deployment

OpenTrain is designed for cloud deployment with minimal configuration:

### Option 1: Render + Vercel (Recommended)

#### 1. Coordinator on Render

1. Fork this repository
2. Go to [render.com](https://render.com) → **New** → **Blueprint**
3. Connect your forked repo
4. Render automatically detects `render.yaml` and creates the coordinator service
5. In service **Environment** tab, set:
   - `ALLOWED_ORIGINS` = your Vercel dashboard URL (e.g., `https://your-app.vercel.app`)
6. Note the coordinator's public URL (e.g., `https://opentrain-coordinator.onrender.com`)

#### 2. Dashboard on Vercel

1. Go to [vercel.com](https://vercel.com) → **New Project**
2. Import your forked repo
3. Set **Root Directory** to `web-dashboard`
4. Update `vercel.json` in your repo:
   ```json
   {
     "rewrites": [
       {
         "source": "/api/:path*",
         "destination": "https://YOUR-RENDER-URL.onrender.com/:path*"
       }
     ]
   }
   ```
5. Deploy

#### 3. Workers Anywhere

Run workers on any machine with Docker:

```bash
# Build the worker image
cd worker
docker build -t opentrain/worker .

# Run a worker node
docker run opentrain/worker --server https://opentrain.onrender.com
```

### Option 2: Local Production

For self-hosted deployments:

```bash
# Start coordinator
cd coordinator
pip install -r requirements.txt
ALLOWED_ORIGINS="http://localhost:3000" uvicorn main:app --host 0.0.0.0 --port 8000

# Start dashboard (separate terminal)
cd web-dashboard
npm install && npm run dev

# Start workers (separate terminals)
cd worker
pip install -r requirements.txt
python worker.py --server http://localhost:8000
```

## Local Development

### Individual Services

```bash
# Coordinator
cd coordinator
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Dashboard
cd web-dashboard
npm install && npm run dev

# Worker
cd worker
pip install -r requirements.txt
python worker.py --server http://localhost:8000
```

### Testing with Multiple Workers

```bash
# Scale workers with docker-compose
docker compose up --scale worker-1=3 --scale worker-2=2
```

### Development Tools

- **API Documentation**: Visit `http://localhost:8000/docs` for interactive Swagger UI
- **Database Inspection**: SQLite database stored in `coordinator/data/opentrain.db`
- **Logs**: All services log to stdout/stderr
- **Hot Reload**: Coordinator and dashboard support hot reloading

## API Documentation

The coordinator provides a complete REST API:

### Jobs
- `GET /jobs` - List all jobs
- `POST /jobs` - Submit new job
- `GET /jobs/{id}` - Get job details
- `GET /jobs/{id}/result` - Download results
- `GET /jobs/{id}/result/summary` - Get result metadata

### Tasks
- `GET /tasks/next?worker_id={id}` - Pull next task
- `POST /tasks/{id}/result` - Submit task result
- `POST /tasks/{id}/fail` - Report task failure

### Workers
- `POST /workers/register` - Register worker
- `POST /workers/heartbeat` - Send heartbeat
- `GET /workers` - List workers

### Health
- `GET /` - Service info
- `GET /health` - Health check

Full OpenAPI specification available at `/docs` when running locally.

## Contributing

We welcome contributions! OpenTrain is designed to be easy to extend.

### Ways to Contribute

- **New Workloads**: Add ML processing capabilities
- **Dashboard Improvements**: Better UI/UX, charts, themes
- **Coordinator Features**: Priority scheduling, worker capabilities
- **Documentation**: Guides, tutorials, translations
- **Testing**: Integration tests, performance benchmarks

### Development Setup

```bash
# Fork and clone
git clone https://github.com/your-username/OpenTrain.git
cd OpenTrain

# Set up pre-commit hooks (optional)
pip install pre-commit
pre-commit install

# Follow local development instructions above
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed contribution guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Built with [FastAPI](https://fastapi.tiangolo.com/), [Next.js](https://nextjs.org/), and [SQLAlchemy](https://sqlalchemy.org/)
- ML workloads powered by [sentence-transformers](https://sbert.net/)
- Inspired by distributed computing platforms like BOINC and HTCondor

---

**OpenTrain** - Democratizing distributed ML computation through volunteer computing.
