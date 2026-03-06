# OpenTrain

Distributed ML compute coordinator. Workers pull tasks, the coordinator orchestrates, the dashboard observes.

## Deployment

### 1. Coordinator → Render

1. Push this repo to GitHub.
2. Go to [render.com](https://render.com) → **New** → **Blueprint** → connect repo.
3. Render reads `render.yaml` and creates the `opentrain-coordinator` web service automatically.
4. Under the service's **Environment** tab, set:
   - `ALLOWED_ORIGINS` = your Vercel dashboard URL (e.g. `https://opentrain.vercel.app`)
5. Copy the coordinator's public URL from the Render dashboard (e.g. `https://opentrain-coordinator.onrender.com`).

### 2. Dashboard → Vercel

1. Go to [vercel.com](https://vercel.com) → **New Project** → import this repo.
2. Set **Root Directory** to `web-dashboard`.
3. No environment variables needed — the `/api` rewrite proxy in `vercel.json` forwards requests to Render.
4. **Update `vercel.json`**: replace `https://opentrain-coordinator.onrender.com` with your actual Render URL.
5. Deploy.

### 3. Workers → Docker (volunteer machines)

```bash
docker run opentrain/worker --server https://opentrain-coordinator.onrender.com
```

Or build locally:

```bash
cd worker
docker build -t opentrain/worker .
docker run opentrain/worker --server https://opentrain-coordinator.onrender.com
```

---

## Local Development

```bash
# Start everything with Docker Compose
docker compose up --build

# Coordinator: http://localhost:8000
# Dashboard:   http://localhost:3000
# API docs:    http://localhost:8000/docs
```

Or run services individually:

```bash
# Coordinator
cd coordinator
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Dashboard (separate terminal)
cd web-dashboard
cp .env.example .env.local   # edit if needed
npm install && npm run dev

# Worker (separate terminal)
cd worker
pip install -r requirements.txt
python worker.py --server http://localhost:8000
```

---

## Architecture

```
[Vercel Dashboard] ──/api/*──→ [Render Coordinator] ←── [Worker nodes]
                                     │
                              SQLite + /data/results
```

- **Coordinator** (`coordinator/`): FastAPI + SQLite + APScheduler. Manages jobs, tasks, workers.
- **Dashboard** (`web-dashboard/`): Next.js. Proxies all API calls through Vercel rewrites to avoid CORS.
- **Worker** (`worker/`): Python script. Registers with coordinator, polls for tasks, runs ML locally.

## Adding a Workload Type

See [CONTRIBUTING.md](CONTRIBUTING.md) — it takes ~10 lines across 4 files.
