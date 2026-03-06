import Head from 'next/head';
import { useEffect, useState } from 'react';
import { api, Worker } from '../lib/api';

function fmt(iso: string) {
  return new Date(iso).toLocaleString('en-US', {
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  });
}

function timeSince(iso: string) {
  const secs = Math.floor((Date.now() - new Date(iso).getTime()) / 1000);
  if (secs < 60) return `${secs}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  return `${Math.floor(secs / 3600)}h ago`;
}

function StatusBadge({ status }: { status: string }) {
  return (
    <span className={`badge ${status}`}>
      <span className="badge-dot" />
      {status}
    </span>
  );
}

const COORDINATOR_URL =
  process.env.NEXT_PUBLIC_COORDINATOR_URL ?? 'http://localhost:8000';

export default function WorkersPage() {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [, setTick] = useState(0); // force re-render for live timestamps
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<
    'all' | 'idle' | 'busy' | 'offline'
  >('all');

  const fetchWorkers = () => {
    api.workers
      .list()
      .then(setWorkers)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchWorkers();
    const dataInterval = setInterval(fetchWorkers, 3000);
    const tickInterval = setInterval(() => setTick((t) => t + 1), 1000); // re-render timestamps
    return () => {
      clearInterval(dataInterval);
      clearInterval(tickInterval);
    };
  }, []);

  const idle = workers.filter((w) => w.status === 'idle').length;
  const busy = workers.filter((w) => w.status === 'busy').length;
  const offline = workers.filter((w) => w.status === 'offline').length;
  const online = idle + busy;

  const filteredWorkers = workers.filter((w) => {
    if (statusFilter !== 'all' && w.status !== statusFilter) return false;
    if (search.trim()) {
      const needle = search.toLowerCase();
      return (
        w.id.includes(needle) || (w.hostname || '').toLowerCase().includes(needle)
      );
    }
    return true;
  });

  return (
    <>
      <Head>
        <title>Workers — OpenTrain</title>
      </Head>

      <div className="page">
        <div className="page-header">
          <div>
            <div className="page-title">Network</div>
            <h1 className="page-heading">Worker Nodes</h1>
          </div>
        </div>

        {/* Stats */}
        <div className="stats-grid">
          <div className="stat">
            <div className="stat-label">Online</div>
            <div className={`stat-value${online > 0 ? ' green' : ''}`}>{online}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Busy</div>
            <div className={`stat-value${busy > 0 ? ' accent' : ''}`}>{busy}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Idle</div>
            <div className="stat-value">{idle}</div>
          </div>
          <div className="stat">
            <div className="stat-label">Offline</div>
            <div className={`stat-value${offline > 0 ? ' red' : ''}`}>{offline}</div>
          </div>
        </div>

        {/* Join command */}
        <div className="card" style={{ marginBottom: 16 }}>
          <div className="card-header">
            <span className="card-label">Add a Worker</span>
            <span
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 10,
                color: 'var(--text-muted)',
              }}
            >
              Run on any volunteer machine
            </span>
          </div>

          <div className="code-block" style={{ fontSize: 12 }}>
            <span style={{ color: 'var(--text-muted)' }}>$ </span>
            <span>docker run opentrain/worker </span>
            <span style={{ color: 'var(--accent)' }}>--server {COORDINATOR_URL} </span>
            <span style={{ color: 'var(--green)' }}>--token your-token</span>
          </div>

          <div
            style={{
              marginTop: 8,
              fontFamily: 'var(--font-mono)',
              fontSize: 10,
              color: 'var(--text-muted)',
            }}
          >
            Workers register automatically and begin polling for tasks immediately after startup.
          </div>
        </div>

        {!loading && workers.length === 0 ? (
          <div className="empty">
            <div className="empty-icon">⬡</div>
            <div>No workers registered yet</div>
            <div style={{ marginTop: 4, color: 'var(--text-muted)', fontSize: 11 }}>
              Run the Docker command above to connect your first worker.
            </div>
          </div>
        ) : filteredWorkers.length === 0 ? (
          <div className="empty">
            <div className="empty-icon">🔍</div>
            <div>No workers match your filters</div>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Worker ID</th>
                  <th>Hostname</th>
                  <th>Status</th>
                  <th>Last Heartbeat</th>
                  <th>Tasks Done</th>
                  <th>Registered</th>
                </tr>
              </thead>
              <tbody>
                {filteredWorkers.map((w) => (
                  <tr key={w.id} style={{ opacity: w.status === 'offline' ? 0.5 : 1 }}>
                    <td className="primary mono">{w.id.slice(0, 8)}…</td>
                    <td className="mono">{w.hostname ?? '—'}</td>
                    <td>
                      <StatusBadge status={w.status} />
                    </td>
                    <td className="mono">
                      <span
                        style={{
                          color:
                            w.status === 'offline'
                              ? 'var(--red)'
                              : 'var(--text-secondary)',
                        }}
                      >
                        {timeSince(w.last_heartbeat)}
                      </span>
                      <span
                        style={{
                          color: 'var(--text-muted)',
                          marginLeft: 8,
                          fontSize: 10,
                        }}
                      >
                        {fmt(w.last_heartbeat)}
                      </span>
                    </td>
                    <td
                      className="mono"
                      style={{
                        color: w.tasks_done > 0 ? 'var(--green)' : 'var(--text-muted)',
                      }}
                    >
                      {w.tasks_done.toLocaleString()}
                    </td>
                    <td className="mono">{fmt(w.registered_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {error ? (
          <div className="empty" style={{ marginTop: 12 }}>
            <div style={{ color: 'var(--red)' }}>{error}</div>
          </div>
        ) : null}
      </div>
    </>
  );
}