/**
 * api.ts — Typed client for the OpenTrain coordinator REST API.
 *
 * Deployment note (Vercel):
 *   In production, NEXT_PUBLIC_COORDINATOR_URL should be left unset.
 *   All API calls will go to /api/... which Vercel rewrites to the
 *   Render coordinator URL (configured in vercel.json). This avoids
 *   CORS issues entirely — the browser never directly contacts Render.
 *
 *   For local dev, set NEXT_PUBLIC_COORDINATOR_URL=http://localhost:8000
 *   in web-dashboard/.env.local.
 */

const BASE =
  typeof window === "undefined"
    ? ""  // SSR: no outbound fetch needed (all pages are client-rendered)
    : process.env.NEXT_PUBLIC_COORDINATOR_URL
      ? process.env.NEXT_PUBLIC_COORDINATOR_URL.replace(/\/$/, "")
      : "/api"; // production: use Vercel rewrite proxy

// ── Types ──────────────────────────────────────────────────────────────────

export type JobStatus    = "pending" | "in_progress" | "completed" | "failed";
export type TaskStatus   = "pending" | "assigned" | "completed" | "failed";
export type WorkerStatus = "idle" | "busy" | "offline";

export interface Job {
  id: string;
  status: JobStatus;
  job_type: string;
  chunk_size: number;
  total_tasks: number;
  done_tasks: number;
  created_at: string;
  completed_at: string | null;
  progress_pct: number;
}

export interface TaskSummary {
  id: string;
  task_index: number;
  status: TaskStatus;
  worker_id: string | null;
  assigned_at: string | null;
  completed_at: string | null;
  attempts: number;
}

export interface JobDetail extends Job {
  tasks: TaskSummary[];
}

export interface Worker {
  id: string;
  status: WorkerStatus;
  last_heartbeat: string;
  tasks_done: number;
  registered_at: string;
  hostname: string | null;
}

export interface ResultSummary {
  job_id: string;
  job_type: string;
  total_tasks: number;
  total_items: number;
  wall_seconds: number;
  completed_at: string;
  artifact_size_bytes: number;
}

export interface JobCreate {
  job_type: string;
  dataset_text: string;
  chunk_size: number;
}

// ── Helpers ────────────────────────────────────────────────────────────────

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...init?.headers },
    ...init,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

// ── API ────────────────────────────────────────────────────────────────────

export const api = {
  jobs: {
    list:          ()                   => request<Job[]>("/jobs"),
    get:           (id: string)         => request<JobDetail>(`/jobs/${id}`),
    create:        (body: JobCreate)    => request<Job>("/jobs", { method: "POST", body: JSON.stringify(body) }),
    resultSummary: (id: string)         => request<ResultSummary>(`/jobs/${id}/result/summary`),
    downloadUrl:   (id: string)         => `${BASE}/jobs/${id}/result`,
  },

  workers: {
    list: () => request<Worker[]>("/workers"),
  },

  health: {
    check: () => request<{ status: string }>("/health"),
  },
};
