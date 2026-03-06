import Head from 'next/head';
import { useRouter } from 'next/router';
import { useState } from 'react';
import { api } from '../lib/api';

const JOB_TYPES = [
  { value: 'embedding',  label: 'Embedding Generation',  desc: 'Generate sentence embeddings using all-MiniLM-L6-v2' },
  { value: 'sentiment',  label: 'Sentiment Analysis',    desc: 'Classify text sentiment as positive/negative/neutral' },
  { value: 'tokenize',   label: 'Tokenization',          desc: 'Whitespace-tokenize each line of text' },
  { value: 'preprocess', label: 'Preprocessing',         desc: 'Lowercase + strip each line of text' },
];

const DATA_FORMATS = [
  { value: 'text', label: 'Plain Text', desc: 'One item per line' },
  { value: 'csv',  label: 'CSV Data',   desc: 'CSV format with headers' },
  { value: 'json', label: 'JSON Data',  desc: 'JSON array or object' },
];

const EXAMPLE_CSV = `text,category
I love this product,positive
This is terrible,negative
Just average,neutral
Best experience ever,positive
Worst purchase ever,negative`;

const EXAMPLE_JSON = `[
  {"text": "I love this product", "category": "positive"},
  {"text": "This is terrible", "category": "negative"},
  {"text": "Just average", "category": "neutral"}
]`;

export default function SubmitPage() {
  const router = useRouter();

  const [jobType,      setJobType]      = useState('embedding');
  const [dataFormat,   setDataFormat]   = useState('text');
  const [file,         setFile]         = useState<File | null>(null);
  const [chunkSize,    setChunkSize]    = useState(100);
  const [submitting,   setSubmitting]   = useState(false);
  const [error,        setError]        = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!file) { setError('Please select a file.'); return; }
    setError(null);
    setSubmitting(true);
    try {
      const job = await api.jobs.create({
        job_type: jobType,
        file: file,
        chunk_size: chunkSize,
        data_format: dataFormat,
        config: {},
      });
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

            {/* Data format selector */}
            <div className="card">
              <div className="card-header">
                <span className="card-label">Data Format</span>
              </div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 8 }}>
                {DATA_FORMATS.map(df => (
                  <label
                    key={df.value}
                    style={{
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 6,
                      padding: '10px',
                      borderRadius: 3,
                      border: '1px solid',
                      borderColor: dataFormat === df.value ? 'var(--accent)' : 'var(--border)',
                      background: dataFormat === df.value ? 'var(--accent-glow)' : 'transparent',
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                  >
                    <input
                      type="radio"
                      name="data_format"
                      value={df.value}
                      checked={dataFormat === df.value}
                      onChange={() => setDataFormat(df.value)}
                      style={{ accentColor: 'var(--accent)' }}
                    />
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, fontWeight: 600 }}>{df.label}</div>
                    <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-muted)' }}>{df.desc}</div>
                  </label>
                ))}
              </div>
            </div>

            {/* Dataset */}
            <div className="card">
              <div className="card-header">
                <span className="card-label">Dataset File</span>
              </div>
              <div className="form-group" style={{ marginBottom: 0 }}>
                <input
                  type="file"
                  accept={dataFormat === 'csv' ? '.csv' : dataFormat === 'json' ? '.json' : '.txt,.text'}
                  onChange={e => setFile(e.target.files?.[0] || null)}
                  style={{ fontFamily: 'var(--font-mono)', fontSize: 12 }}
                />
                <div className="form-hint">
                  {dataFormat === 'csv' && 'Upload a CSV file with headers.'}
                  {dataFormat === 'json' && 'Upload a JSON file (array or object).'}
                  {dataFormat === 'text' && 'Upload a text file (one item per line).'}
                </div>
              </div>
            </div>

            {error && <div className="alert alert-error">{error}</div>}

            <button
              className="btn btn-primary"
              onClick={handleSubmit}
              disabled={submitting || !file}
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
              <div className="form-group" style={{ marginBottom: 0 }}>
                <input
                  type="range"
                  min="1"
                  max="1000"
                  value={chunkSize}
                  onChange={e => setChunkSize(parseInt(e.target.value))}
                  style={{ width: '100%' }}
                />
                <div className="form-hint">
                  How many {dataFormat === 'csv' ? 'rows' : 'lines'} per shard{dataFormat === 'csv' ? ' (excluding header)' : ''}.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}