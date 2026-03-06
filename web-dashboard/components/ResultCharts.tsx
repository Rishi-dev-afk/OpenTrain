import React from 'react';
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

interface SentimentChartProps {
  sentimentData: any;
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

