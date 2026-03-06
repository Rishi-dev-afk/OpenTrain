import Head from 'next/head';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { api, JobDetail, ResultSummary, TaskSummary } from '../../lib/api';

function fmt(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false,
  });
}

function StatusBadge({ status }: { status: string }) {
  const s = status.replace('_', '-');
  return (
    <span className={`badge ${s}`}>
      <span className="badge-dot" />
      {status.replace('_', ' ')}
    </span>
  );
}

function TaskRow({ task }: { task: TaskSummary }) {
  return (
    <tr>
      <td className="mono" style={{ color: 'var(--text-muted)' }}>#{task.task_index}</td>
      <td className="mono primary">{task.id.slice(0, 8)}…</td>
      <td><StatusBadge status={task.status} /></td>
      <td className="mono">{task.worker_id ? task.worker_id.slice(0, 8) + '…' : '—'}</td>
      <td className="mono">{fmt(task.assigned_at)}</td>
      <td className="mono">{fmt(task.completed_at)}</td>
      <td className="mono" style={{ color: task.attempts > 1 ? 'var(--yellow)' : 'var(--text-muted)' }}>
        {task.attempts}
      </td>
    </tr>
  );
}

export default function JobDetailPage() {
  const router                        = useRouter();
  const { id }                        = router.query as { id: string };
  const [job, setJob]                 = useState<JobDetail | null>(null);
  const [summary, setSummary]         = useState<ResultSummary | null>(null);
  const [isStatsJob, setIsStatsJob]   = useState(false);
  const [loading, setLoading]         = useState(true);
  const [error, setError]             = useState<string | null>(null);
  const [filter, setFilter]           = useState<string>('all');

  const fetchJob = () => {
    if (!id) return;
    api.jobs.get(id)
      .then(data => {
        setJob(data);
        setIsStatsJob(data.job_type === 'stats');
        setLoading(false);
        // Fetch result summary once job completes
        if (data.status === 'completed' && !summary) {
          api.jobs.resultSummary(id).then(setSummary).catch(() => {});
        }
      })
      .catch(e => { setError(e.message); setLoading(false); });
  };

  useEffect(() => {
    fetchJob();
    const interval = setInterval(fetchJob, 2000);
    return () => clearInterval(interval);
  }, [id]);

  if (loading) return (
    <div className="page" style={{ display: 'flex', alignItems: 'center', gap: 12, color: 'var(--text-secondary)' }}>
      <div className="spinner" /> Loading job…
    </div>
  );

  if (error || !job) return (
    <div className="page">
      <div className="alert alert-error">{error ?? 'Job not found'}</div>
      <Link href="/" style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontSize: 12, marginTop: 12, display: 'inline-block' }}>
        ← Back to jobs
      </Link>
    </div>
  );

  if (isStatsJob) return (
    <div className="page">
      <div className="alert alert-error">Statistical analysis jobs are no longer visible.</div>
      <Link href="/" style={{ color: 'var(--accent)', fontFamily: 'var(--font-mono)', fontSize: 12, marginTop: 12, display: 'inline-block' }}>
        ← Back to jobs
      </Link>
    </div>
  );

  const isLive     = job.status === 'in_progress';
  const isDone     = job.status === 'completed';
  const isFailed   = job.status === 'failed';
  const tasks      = job.tasks ?? [];
  const filtered   = filter === 'all' ? tasks : tasks.filter(t => t.status === filter);

  const taskCounts = tasks.reduce((acc, t) => {
    acc[t.status] = (acc[t.status] ?? 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  return (
    <>
      <Head><title>Job {job.id.slice(0, 8)} — OpenTrain</title></Head>
      <div className="page">

        {/* Header */}
        <div className="page-header">
          <div>
            <div className="page-title">
              <Link href="/" style={{ color: 'var(--text-muted)', textDecoration: 'none' }}>Jobs</Link>
              {' / '}
              {job.id.slice(0, 8)}…
            </div>
            <h1 className="page-heading" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              {job.job_type}
              <StatusBadge status={job.status} />
              {isLive && <div className="spinner" style={{ width: 14, height: 14 }} />}
            </h1>
          </div>
          {isDone && (
            <a
              href={api.jobs.downloadUrl(job.id)}
              className="btn btn-primary"
              download
            >
              ↓ Download Result
            </a>
          )}
        </div>

        {/* Stats */}
        <div className="stats-grid">
          <div className="stat">
            <div className="stat-label">Progress</div>
            <div className={`stat-value${isDone ? ' green' : isLive ? ' accent' : ''}`}>
              {job.progress_pct.toFixed(1)}%
            </div>
          </div>
          <div className="stat">
            <div className="stat-label">Tasks</div>
            <div className="stat-value">{job.done_tasks}<span style={{ color: 'var(--text-muted)', fontSize: 14 }}>/{job.total_tasks}</span></div>
          </div>
          <div className="stat">
            <div className="stat-label">Chunk Size</div>
            <div className="stat-value">{job.chunk_size}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Created</div>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>{fmt(job.created_at)}</div>
          </div>
          {summary && (
            <>
              <div className="stat">
                <div className="stat-label">Total Items</div>
                <div className="stat-value green">{summary.total_items.toLocaleString()}</div>
              </div>
              <div className="stat">
                <div className="stat-label">Wall Time</div>
                <div className="stat-value">{summary.wall_seconds.toFixed(1)}<span style={{ color: 'var(--text-muted)', fontSize: 14 }}>s</span></div>
              </div>
            </>
          )}
        </div>

        {/* Progress bar */}
        <div style={{ marginBottom: 24 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
              {job.done_tasks} of {job.total_tasks} tasks complete
            </span>
            <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: isDone ? 'var(--green)' : 'var(--accent)' }}>
              {job.progress_pct.toFixed(1)}%
            </span>
          </div>
          <div className="progress-wrap" style={{ height: 6 }}>
            <div
              className={`progress-bar${isDone ? ' complete' : ''}`}
              style={{ width: `${job.progress_pct}%` }}
            />
          </div>
        </div>


        {/* Result summary download card */}
        {isDone && summary && (
          <div className="card" style={{ marginBottom: 16, borderColor: 'var(--green-dim)' }}>
            <div className="card-header">
              <span className="card-label" style={{ color: 'var(--green)' }}>✓ Result Ready</span>
              <a href={api.jobs.downloadUrl(job.id)} className="btn btn-ghost" style={{ fontSize: 10, padding: '4px 10px' }} download>
                ↓ Download JSON
              </a>
            </div>
            <div style={{ display: 'flex', gap: 32, fontFamily: 'var(--font-mono)', fontSize: 12, color: 'var(--text-secondary)' }}>
              <span><span style={{ color: 'var(--text-muted)' }}>items </span>{summary.total_items.toLocaleString()}</span>
              <span><span style={{ color: 'var(--text-muted)' }}>wall time </span>{summary.wall_seconds.toFixed(2)}s</span>
              <span><span style={{ color: 'var(--text-muted)' }}>size </span>{(summary.artifact_size_bytes / 1024).toFixed(1)} KB</span>
              <span><span style={{ color: 'var(--text-muted)' }}>type </span>{summary.job_type}</span>
            </div>
          </div>
        )}

        {/* Tasks table */}
        <div className="card">
          <div className="card-header">
            <span className="card-label">Task Breakdown</span>
            <div style={{ display: 'flex', gap: 4 }}>
              {(['all', 'pending', 'assigned', 'completed', 'failed'] as const).map(s => (
                <button
                  key={s}
                  onClick={() => setFilter(s)}
                  style={{
                    fontFamily: 'var(--font-mono)',
                    fontSize: 10,
                    fontWeight: 600,
                    letterSpacing: '0.08em',
                    textTransform: 'uppercase',
                    padding: '3px 8px',
                    borderRadius: 2,
                    border: '1px solid',
                    cursor: 'pointer',
                    borderColor: filter === s ? 'var(--accent)' : 'var(--border)',
                    background:  filter === s ? 'var(--accent-glow)' : 'transparent',
                    color:       filter === s ? 'var(--accent)' : 'var(--text-muted)',
                  }}
                >
                  {s}{s !== 'all' && taskCounts[s] ? ` (${taskCounts[s]})` : ''}
                </button>
              ))}
            </div>
          </div>

          {filtered.length === 0 ? (
            <div className="empty" style={{ padding: '32px 20px' }}>
              <div>No {filter !== 'all' ? filter : ''} tasks</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Task ID</th>
                    <th>Status</th>
                    <th>Worker</th>
                    <th>Assigned</th>
                    <th>Completed</th>
                    <th>Attempts</th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.map(task => <TaskRow key={task.id} task={task} />)}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
