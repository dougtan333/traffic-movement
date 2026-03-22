/**
 * PTPatronageChart — monthly public transport patronage trend.
 * Toggleable between stacked area (total) and line trend (per mode).
 * Victoria only — all data is Melbourne metro + regional VIC.
 */
import { useState } from 'react';
import {
  ResponsiveContainer, AreaChart, Area, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import './PTPatronageChart.css';

const MODE_COLORS = {
  metro_train: '#1B3A5C',
  metro_tram: '#2A9D8F',
  metro_bus: '#E9C46A',
  regional_train: '#F4A261',
  regional_bus: '#6D2E46',
};

const MODE_LABELS = {
  metro_train: 'Metro train',
  metro_tram: 'Metro tram',
  metro_bus: 'Metro bus',
  regional_train: 'Regional train',
  regional_bus: 'Regional bus',
};

const formatM = (v) => `${(v / 1_000_000).toFixed(1)}M`;

/**
 * Build a short commentary paragraph from the patronage data.
 * Identifies: latest month, peak month, dominant mode, and trend direction.
 */
function buildCommentary(chartData) {
  if (!chartData?.length) return null;

  const latest = chartData[chartData.length - 1];
  const peak = chartData.reduce((max, d) => d.total > max.total ? d : max, chartData[0]);

  // Dominant mode in latest month
  const modes = ['metro_train', 'metro_tram', 'metro_bus', 'regional_train', 'regional_bus'];
  const topMode = modes.reduce((best, m) => (latest[m] || 0) > (latest[best] || 0) ? m : best, modes[0]);
  const topModePct = ((latest[topMode] / latest.total) * 100).toFixed(0);

  // YoY comparison: same month last year
  const priorYear = chartData.find(
    d => d.month === latest.month && d.year === latest.year - 1
  );
  let yoyNote = '';
  if (priorYear) {
    const yoyPct = (((latest.total - priorYear.total) / priorYear.total) * 100).toFixed(1);
    const dir = yoyPct > 0 ? 'up' : yoyPct < 0 ? 'down' : 'flat';
    yoyNote = ` That's ${dir === 'flat' ? 'flat' : `${dir} ${Math.abs(yoyPct)}%`} on the same month last year.`;
  }

  // 3-month trend
  const recent3 = chartData.slice(-3);
  let trendNote = '';
  if (recent3.length === 3) {
    const rising = recent3[2].total > recent3[0].total;
    const delta = (((recent3[2].total - recent3[0].total) / recent3[0].total) * 100).toFixed(1);
    trendNote = ` The 3-month trend is ${rising ? 'rising' : 'declining'} (${delta > 0 ? '+' : ''}${delta}%).`;
  }

  return `${latest.label} recorded ${formatM(latest.total)} total trips. ${MODE_LABELS[topMode]} is the dominant mode at ${topModePct}% of all patronage.${yoyNote}${trendNote} Peak patronage was ${peak.label} with ${formatM(peak.total)} trips.`;
}

/**
 * Custom tick: show "Jan '24" at January boundaries, skip other months
 * to prevent label overlap on the x-axis.
 */
function tickFormatter(label) {
  if (!label) return '';
  const parts = label.split(' ');
  if (parts.length < 2) return label;
  const mon = parts[0];
  const yr = parts[1];
  // Show Jan of every year as anchor, plus Jul for mid-year reference
  if (mon === 'Jan') return `Jan '${yr.slice(2)}`;
  if (mon === 'Jul') return `Jul '${yr.slice(2)}`;
  return '';
}

const MODES = ['metro_train', 'metro_tram', 'metro_bus', 'regional_train', 'regional_bus'];

const VIEW_TYPES = [
  { value: 'stacked', label: 'Stacked' },
  { value: 'trend', label: 'Trend' },
];

export default function PTPatronageChart() {
  const [view, setView] = useState('stacked');
  const { data, loading, error } = useTrafficData('/api/transport/pt-monthly', {});

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  const chartData = data.data;
  const commentary = buildCommentary(chartData);

  return (
    <div className="pt-patronage">
      <div className="pt-summary">
        <span className="pt-latest">
          Latest: <strong>{chartData[chartData.length - 1].label}</strong> —{' '}
          {formatM(chartData[chartData.length - 1].total)} total trips
        </span>
      </div>
      {commentary && <p className="pt-commentary">{commentary}</p>}
      <div className="chart-container">
        <div className="day-type-toggle">
          {VIEW_TYPES.map(vt => (
            <button
              key={vt.value}
              className={`toggle-btn ${view === vt.value ? 'active' : ''}`}
              onClick={() => setView(vt.value)}
            >
              {vt.label}
            </button>
          ))}
        </div>
        <ResponsiveContainer width="100%" height={300}>
          {view === 'stacked' ? (
            <AreaChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} tickFormatter={tickFormatter} interval={0} />
              <YAxis tickFormatter={formatM} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v, name) => [formatM(v), MODE_LABELS[name] || name]} labelFormatter={(l) => l} />
              <Legend formatter={(v) => MODE_LABELS[v] || v} />
              {MODES.map(m => (
                <Area key={m} type="monotone" dataKey={m} stackId="1" stroke={MODE_COLORS[m]} fill={MODE_COLORS[m]} fillOpacity={0.8} />
              ))}
            </AreaChart>
          ) : (
            <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} tickFormatter={tickFormatter} interval={0} />
              <YAxis tickFormatter={formatM} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v, name) => [formatM(v), MODE_LABELS[name] || name]} labelFormatter={(l) => l} />
              <Legend formatter={(v) => MODE_LABELS[v] || v} />
              {MODES.map(m => (
                <Line key={m} type="monotone" dataKey={m} stroke={MODE_COLORS[m]} strokeWidth={2} dot={false} />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </div>
  );
}
