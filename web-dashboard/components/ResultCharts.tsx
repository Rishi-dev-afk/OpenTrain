import React from 'react';
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer
} from 'recharts';

interface SentimentChartProps {
  sentimentData: any;
}

interface StatsChartProps {
  statsData: any;
}

export function SentimentChart({ sentimentData }: SentimentChartProps) {
  if (!sentimentData?.summary) return null;

  const { summary } = sentimentData;
  const chartData = [
    { name: 'Positive', value: summary.positive_count, fill: '#3FB950' },
    { name: 'Negative', value: summary.negative_count, fill: '#F85149' },
    { name: 'Neutral', value: summary.neutral_count, fill: '#58A6FF' },
  ];

  const barData = [
    { label: 'Positive', percentage: summary.positive_pct },
    { label: 'Negative', percentage: summary.negative_pct },
    { label: 'Neutral', percentage: summary.neutral_pct },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div>
        <h3 style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Sentiment Distribution</h3>
        <ResponsiveContainer width="100%" height={300}>
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              labelLine={false}
              label={({ name, percentage }) => `${name}: ${percentage}%`}
              outerRadius={80}
              fill="#8884d8"
              dataKey="value"
            >
              {chartData.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.fill} />
              ))}
            </Pie>
            <Tooltip />
          </PieChart>
        </ResponsiveContainer>
      </div>

      <div>
        <h3 style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Percentage Breakdown</h3>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={barData}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis dataKey="label" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="percentage" fill="var(--accent)" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
        <div style={{ padding: 12, background: 'var(--bg-hover)', borderRadius: 4 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>Avg Confidence</div>
          <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--accent)', marginTop: 4 }}>
            {(summary.avg_confidence * 100).toFixed(1)}%
          </div>
        </div>
        <div style={{ padding: 12, background: 'var(--bg-hover)', borderRadius: 4 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>Total Documents</div>
          <div style={{ fontSize: 18, fontWeight: 600, color: 'var(--text-primary)', marginTop: 4 }}>
            {summary.total_documents.toLocaleString()}
          </div>
        </div>
        <div style={{ padding: 12, background: 'var(--bg-hover)', borderRadius: 4 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>Positive Rate</div>
          <div style={{ fontSize: 18, fontWeight: 600, color: '#3FB950', marginTop: 4 }}>
            {summary.positive_pct.toFixed(1)}%
          </div>
        </div>
      </div>
    </div>
  );
}

export function StatsChart({ statsData }: StatsChartProps) {
  if (!statsData?.stats) return null;

  const { stats } = statsData;
  const topWordsData = (stats.top_20_words || []).slice(0, 10).map((entry: [string, number]) => ({
    word: entry[0],
    count: entry[1],
  }));

  const topBigramsData = (stats.top_20_bigrams || []).slice(0, 8).map((entry: [string, number]) => ({
    bigram: entry[0],
    count: entry[1],
  }));

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        <div style={{ padding: 16, background: 'var(--bg-hover)', borderRadius: 4 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Total Texts</div>
          <div style={{ fontSize: 28, fontWeight: 600, color: 'var(--accent)' }}>
            {stats.total_texts?.toLocaleString()}
          </div>
        </div>
        <div style={{ padding: 16, background: 'var(--bg-hover)', borderRadius: 4 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Total Words</div>
          <div style={{ fontSize: 28, fontWeight: 600, color: 'var(--text-primary)' }}>
            {stats.total_words?.toLocaleString()}
          </div>
        </div>
        <div style={{ padding: 16, background: 'var(--bg-hover)', borderRadius: 4 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Avg Document Length</div>
          <div style={{ fontSize: 28, fontWeight: 600, color: 'var(--blue)' }}>
            {stats.avg_document_length?.toFixed(1)} chars
          </div>
        </div>
        <div style={{ padding: 16, background: 'var(--bg-hover)', borderRadius: 4 }}>
          <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)', marginBottom: 2 }}>Avg Words/Doc</div>
          <div style={{ fontSize: 28, fontWeight: 600, color: 'var(--green)' }}>
            {stats.avg_words_per_document?.toFixed(1)}
          </div>
        </div>
      </div>

      {topWordsData.length > 0 && (
        <div>
          <h3 style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Top 10 Words</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={topWordsData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="word" width={100} fontSize={12} />
              <Tooltip />
              <Bar dataKey="count" fill="var(--accent)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {topBigramsData.length > 0 && (
        <div>
          <h3 style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Top Bigrams (Word Pairs)</h3>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart data={topBigramsData} layout="vertical">
              <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
              <XAxis type="number" />
              <YAxis type="category" dataKey="bigram" width={150} fontSize={11} />
              <Tooltip />
              <Bar dataKey="count" fill="var(--blue)" radius={[0, 4, 4, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      <div>
        <h3 style={{ fontFamily: 'var(--font-mono)', fontSize: 14, fontWeight: 600, marginBottom: 12 }}>Text Statistics Summary</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12, fontSize: 12 }}>
          <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 4 }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>Min Document Length</div>
            <div style={{ color: 'var(--text-primary)', marginTop: 4, fontWeight: 500 }}>
              {stats.min_length} characters
            </div>
          </div>
          <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 4 }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>Max Document Length</div>
            <div style={{ color: 'var(--text-primary)', marginTop: 4, fontWeight: 500 }}>
              {stats.max_length} characters
            </div>
          </div>
          <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 4 }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>Vocabulary Richness</div>
            <div style={{ color: 'var(--text-primary)', marginTop: 4, fontWeight: 500 }}>
              {(stats.overall_vocabulary_richness || 0).toFixed(4)} (unique words per doc)
            </div>
          </div>
          <div style={{ padding: 12, border: '1px solid var(--border)', borderRadius: 4 }}>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--text-muted)' }}>Avg Sentence Length</div>
            <div style={{ color: 'var(--text-primary)', marginTop: 4, fontWeight: 500 }}>
              {stats.avg_words_per_document?.toFixed(1)} words
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
