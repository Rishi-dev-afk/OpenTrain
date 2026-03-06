import Head from 'next/head';
import { useRouter } from 'next/router';
import { useState } from 'react';
import { api } from '../lib/api';

const JOB_TYPES = [
  { value: 'embedding',  label: 'Embedding Generation',  desc: 'Generate sentence embeddings using all-MiniLM-L6-v2' },
  { value: 'tokenize',   label: 'Tokenization',          desc: 'Whitespace-tokenize each line of text' },
  { value: 'preprocess', label: 'Preprocessing',         desc: 'Lowercase + strip each line of text' },
];

const EXAMPLE_DATASET = `The quick brown fox jumps over the lazy dog.
Machine learning models can process natural language at scale.
Distributed systems allow computation across many volunteer machines.
OpenTrain splits workloads into shards for parallel processing.
Each worker node processes its assigned shard independently.`;

export default function SubmitPage() {
  const router = useRouter();

  const [jobType,     setJobType]     = useState('embedding');
  const [dataset,     setDataset]     = useState('');
  const [chunkSize,   setChunkSize]   = useState(100);
  const [submitting,  setSubmitting]  = useState(false);
  const [error,       setError]       = useState<string | null>(null);

  const lineCount  = dataset.trim() ? dataset.trim().split('\n').filter(l => l.trim()).length : 0;
  const taskCount  = lineCount > 0 ? Math.ceil(lineCount / chunkSize) : 0;

  const handleSubmit = async () => {
    if (!dataset.trim()) { setError('Dataset cannot be empty.'); return; }
    setError(null);
    setSubmitting(true);
    try {
      const job = await api.jobs.create({ job_type: jobType, dataset_text: dataset, chunk_size: chunkSize });
      router.push(`/jobs/${job.id}`);
    } catch (e: any) {
      setError(e.message);
      setSubmitting(false);
    }
  };

  return (
    <>
      <Head><title>Submit Job — OpenTrain</title></Head>
      <div className="page">
        <div className="page-header">
          <div>
            <div className="page-title">Coordinator</div>
            <h1 className="page-heading">Submit Job</h1>
          </div>
        </div>

        <div className="grid-sidebar">
          {/* Left: form */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* Job type selector */}
            <div className="card">
              <div className="card-header">
                <span className="card-label">Job Type</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {JOB_TYPES.map(jt => (
                  <label
                    key={jt.value}
                    style={{
                      display: 'flex',
                      alignItems: 'flex-start',
                      gap: 12,
                      padding: '10px 12px',
                      borderRadius: 3,
                      border: '1px solid',
                      borderColor: jobType === jt.value ? 'var(--accent)' : 'var(--border)',
                      background: jobType === jt.value ? 'var(--accent-glow)' : 'transparent',
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                  >
                    <input
                      type="radio"
                      name="job_type"
                      value={jt.value}
                      checked={jobType === jt.value}
                      onChange={() => setJobType(jt.value)}
                      style={{ marginTop: 2, accentColor: 'var(--accent)' }}
                    />
                    <div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 2 }}>
                        {jt.label}
                      </div>
                      <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>
                        {jt.desc}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Dataset */}
            <div className="card">
              <div className="card-header">
                <span className="card-label">Dataset</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: lineCount > 0 ? 'var(--accent)' : 'var(--text-muted)' }}>
                  {lineCount.toLocaleString()} lines
                </span>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <textarea
                  className="form-textarea"
                  style={{ minHeight: 200, fontSize: 12 }}
                  placeholder="Paste your dataset here — one item per line…"
                  value={dataset}
                  onChange={e => setDataset(e.target.value)}
                  spellCheck={false}
                />
                <div className="form-hint">
                  One text item per line. Empty lines are ignored.{' '}
                  <button
                    onClick={() => setDataset(EXAMPLE_DATASET)}
                    style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontFamily: 'var(--font-mono)', fontSize: 10, padding: 0 }}
                  >
                    Load example →
                  </button>
                </div>
              </div>
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            <button
              className="btn btn-primary"
              onClick={handleSubmit}
              disabled={submitting || lineCount === 0}
              style={{ alignSelf: 'flex-start' }}
            >
              {submitting ? <><div className="spinner" /> Submitting…</> : '→ Submit Job'}
            </button>
          </div>

          {/* Right: config + preview */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>

            {/* Chunk size */}
            <div className="card">
              <div className="card-header">
                <span className="card-label">Chunk Size</span>
                <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: 'var(--accent)' }}>
                  {chunkSize}
                </span>
              </div>
              <input
                type="range"
                min={10} max={1000} step={10}
                value={chunkSize}
                onChange={e => setChunkSize(Number(e.target.value))}
                style={{ width: '100%', accentColor: 'var(--accent)', marginBottom: 8 }}
              />
              <div className="form-hint">Lines per task shard. Smaller = more tasks = more parallelism.</div>
            </div>

            {/* Preview card */}
            <div className="card">
              <div className="card-header">
                <span className="card-label">Job Preview</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {[
                  ['Type',       jobType],
                  ['Lines',      lineCount.toLocaleString()],
                  ['Chunk size', chunkSize],
                  ['Tasks',      taskCount.toLocaleString()],
                ].map(([label, val]) => (
                  <div key={label} style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>{label}</span>
                    <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-primary)', fontWeight: 600 }}>{val}</span>
                  </div>
                ))}
                <div className="divider" style={{ margin: '4px 0' }} />
                <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>
                  {taskCount} tasks will be distributed across available workers.
                </div>
              </div>
            </div>

            {/* Worker join hint */}
            <div className="card">
              <div className="card-header">
                <span className="card-label">Start a Worker</span>
              </div>
              <div className="code-block" style={{ fontSize: 11 }}>
                <div><span className="muted">$</span> docker run opentrain/worker \</div>
                <div style={{ paddingLeft: 16 }}>--server <span className="accent">http://localhost:8000</span> \</div>
                <div style={{ paddingLeft: 16 }}>--token <span className="green">your-token</span></div>
              </div>
            </div>

          </div>
        </div>
      </div>
    </>
  );
}