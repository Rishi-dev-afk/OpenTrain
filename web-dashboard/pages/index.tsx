import Head from 'next/head';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { api, Job } from '../lib/api';

function fmt(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short', day: '2-digit',
    hour: '2-digit', minute: '2-digit', hour12: false,
  });
}

function elapsed(created: string, completed: string | null) {
  const end  = completed ? new Date(completed) : new Date();
  const secs = Math.floor((end.getTime() - new Date(created).getTime()) / 1000);
  if (secs < 60)  return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`;
  return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`;
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

function MiniProgress({ pct, status }: { pct: number; status: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div className="progress-wrap" style={{ width: 80 }}>
        <div
          className={`progress-bar${status === 'completed' ? ' complete' : ''}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', minWidth: 32 }}>
        {pct.toFixed(0)}%
      </span>
    </div>
  );
}

export default function JobsPage() {
  const [jobs, setJobs]       = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState<string | null>(null);
  const [search, setSearch]   = useState('');
  const [statusFilter, setStatusFilter] = useState<'all'|'in_progress'|'completed'|'failed'>('all');

  const fetchJobs = () => {
    api.jobs.list()
      .then(setJobs)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchJobs();
    const id = setInterval(fetchJobs, 3000); // poll every 3s
    return () => clearInterval(id);
  }, []);

  const total     = jobs.length;
  const running   = jobs.filter(j => j.status === 'in_progress').length;
  const completed = jobs.filter(j => j.status === 'completed').length;
  const failed    = jobs.filter(j => j.status === 'failed').length;

  const filteredJobs = jobs
    .filter(j => j.job_type !== 'stats') // hide statistical-analysis jobs
    .filter(j => {
      if (statusFilter !== 'all' && j.status !== statusFilter) return false;
      if (search.trim()) {
        const needle = search.toLowerCase();
        return j.id.includes(needle) || j.job_type.toLowerCase().includes(needle);
      }
      return true;
    });

  return (
    <>
      <Head><title>Jobs — OpenTrain</title></Head>

      <div className="page">
        <div className="page-header">
          <div>
            <div className="page-title">Coordinator</div>
            <h1 className="page-heading">Job Queue</h1>
          </div>
          <Link href="/submit" className="btn btn-primary">
            + New Job
          </Link>
        </div>

        {/* Stats */}
        <div className="stats-grid">
          <div className="stat">
            <div className="stat-label">Total Jobs</div>
            <div className="stat-value">{total}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Running</div>
            <div className={`stat-value${running > 0 ? ' accent' : ''}`}>{running}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Completed</div>
            <div className={`stat-value${completed > 0 ? ' green' : ''}`}>{completed}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Failed</div>
            <div className={`stat-value${failed > 0 ? ' red' : ''}`}>{failed}</div>
          </div>
        </div>

        {/* Table */}
        <div className="card">
          <div className="card-header" style={{ flexDirection: 'column', alignItems: 'start', gap: 8 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12, width: '100%' }}>
              <span className="card-label">All Jobs</span>
              {loading && <div className="spinner" />}
              <input
                type="text"
                placeholder="Search by id or type…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                style={{
                  marginLeft: 'auto',
                  padding: '4px 8px',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 11,
                  border: '1px solid var(--border-bright)',
                  borderRadius: 3,
                  background: 'var(--bg-base)',
                  color: 'var(--text-primary)',
                }}
              />
            </div>
            <div style={{ display: 'flex', gap: 4 }}>
              {(['all', 'in_progress', 'completed', 'failed'] as const).map(s => (
                <button
                  key={s}
                  onClick={() => setStatusFilter(s)}
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
                    borderColor: statusFilter === s ? 'var(--accent)' : 'var(--border)',
                    background:  statusFilter === s ? 'var(--accent-glow)' : 'transparent',
                    color:       statusFilter === s ? 'var(--accent)' : 'var(--text-muted)',
                  }}
                >
                  {s.replace('_', ' ')}{s !== 'all' &&
                    jobs.filter(j => j.status === s).length ? ` (${jobs.filter(j => j.status === s).length})` : ''}
                </button>
              ))}
            </div>
          </div>

          {error && <div className="alert alert-error" style={{ marginBottom: 12 }}>{error}</div>}

          {!loading && jobs.length === 0 ? (
            <div className="empty">
              <div className="empty-icon">⬡</div>
              <div>No jobs yet</div>
              <div style={{ marginTop: 4 }}>
                <Link href="/submit" style={{ color: 'var(--accent)', textDecoration: 'none' }}>
                  Submit your first job →
                </Link>
              </div>
            </div>
          ) : filteredJobs.length === 0 ? (
            <div className="empty">
              <div className="empty-icon">🔍</div>
              <div>No jobs match your filters</div>
            </div>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Job ID</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Progress</th>
                    <th>Tasks</th>
                    <th>Elapsed</th>
                    <th>Created</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filteredJobs.map(job => (
                    <tr
                      key={job.id}
                      onClick={() => window.location.href = `/jobs/${job.id}`}
                      style={{ cursor: 'pointer' }}
                    >
                      <td className="primary mono">{job.id.slice(0, 8)}…</td>
                      <td className="mono">{job.job_type}</td>
                      <td><StatusBadge status={job.status} /></td>
                      <td><MiniProgress pct={job.progress_pct} status={job.status} /></td>
                      <td className="mono">{job.done_tasks}/{job.total_tasks}</td>
                      <td className="mono">{elapsed(job.created_at, job.completed_at)}</td>
                      <td className="mono">{fmt(job.created_at)}</td>
                      <td>
                        <Link href={`/jobs/${job.id}`} className="btn btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }}>
                          View →
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </>
  );
}