/**
 * WeekdayDrift — compares Mon–Fri traffic profile across 2024, 2025, and 2026.
 * Grouped bar chart showing whether specific weekdays are getting busier or quieter.
 * Business hours only, metro core stations, Victoria only.
 */
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend, Cell, ReferenceLine,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import './WeekdayDrift.css';

export default function WeekdayDrift() {
  const { data, loading, error } = useTrafficData('/api/traffic/weekday-drift', {});

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  const chartData = data.data;

  // Find biggest 25→26 mover for commentary (most relevant comparison)
  const withChange = chartData.filter(d => d.change_pct_25_26 != null);
  const sorted = [...withChange].sort((a, b) => Math.abs(b.change_pct_25_26) - Math.abs(a.change_pct_25_26));
  const biggest = sorted[0];
  const smallest = sorted[sorted.length - 1];

  return (
    <div className="weekday-drift">
      <p className="drift-commentary">
        {biggest && smallest ? (
          <>
            {biggest.day} showed the largest 2025→26 shift ({biggest.change_pct_25_26 > 0 ? '+' : ''}{biggest.change_pct_25_26}%),
            while {smallest.day} was the most stable ({smallest.change_pct_25_26 > 0 ? '+' : ''}{smallest.change_pct_25_26}%).
          </>
        ) : null}
        {' '}All values are business hours (7am–6pm), excluding public holidays.
        {data.note_2026 ? <span className="drift-note"> {data.note_2026}.</span> : null}
      </p>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
            <XAxis dataKey="day" tick={{ fontSize: 12 }} />
            <YAxis
              tick={{ fontSize: 11 }}
              domain={['dataMin - 2000', 'dataMax + 2000']}
              label={{ value: 'Vehicles/day/station', angle: -90, position: 'insideLeft', offset: 0, style: { fontSize: 11, fill: '#888' } }}
            />
            <Tooltip
              formatter={(v, name) => {
                const labels = { avg_2024: '2024', avg_2025: '2025', avg_2026: '2026' };
                return [v.toLocaleString(), labels[name] || name];
              }}
            />
            <Legend formatter={(v) => {
              const labels = { avg_2024: '2024', avg_2025: '2025', avg_2026: '2026' };
              return labels[v] || v;
            }} />
            <Bar dataKey="avg_2024" fill="#73726c" radius={[4, 4, 0, 0]} />
            <Bar dataKey="avg_2025" fill="#1D9E75" radius={[4, 4, 0, 0]} />
            <Bar dataKey="avg_2026" fill="#2563eb" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="drift-table">
        <div className="drift-row drift-header">
          <span className="drift-day"></span>
          <span className="drift-values">2024 → 2025 → 2026</span>
          <span className="drift-pct">24→25</span>
          <span className="drift-pct">25→26</span>
        </div>
        {chartData.map(d => (
          <div key={d.day} className="drift-row">
            <span className="drift-day">{d.day}</span>
            <span className="drift-values">{d.avg_2024.toLocaleString()} → {d.avg_2025.toLocaleString()} → {d.avg_2026.toLocaleString()}</span>
            <span className={`drift-pct ${d.change_pct_24_25 > 0 ? 'up' : 'down'}`}>
              {d.change_pct_24_25 > 0 ? '+' : ''}{d.change_pct_24_25}%
            </span>
            <span className={`drift-pct ${d.change_pct_25_26 > 0 ? 'up' : 'down'}`}>
              {d.change_pct_25_26 > 0 ? '+' : ''}{d.change_pct_25_26}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
