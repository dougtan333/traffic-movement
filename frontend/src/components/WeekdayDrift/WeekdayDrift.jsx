/**
 * WeekdayDrift — compares Mon–Fri traffic profile between 2024 and 2025.
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

  // Find biggest mover for commentary
  const sorted = [...chartData].sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct));
  const biggest = sorted[0];
  const smallest = sorted[sorted.length - 1];

  return (
    <div className="weekday-drift">
      <p className="drift-commentary">
        {biggest.day} showed the largest year-on-year shift ({biggest.change_pct > 0 ? '+' : ''}{biggest.change_pct}%), 
        while {smallest.day} was the most stable ({smallest.change_pct > 0 ? '+' : ''}{smallest.change_pct}%). 
        All values are business hours (7am–6pm), excluding public holidays.
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
              formatter={(v, name) => [v.toLocaleString(), name === 'avg_2024' ? '2024' : '2025']}
            />
            <Legend formatter={(v) => v === 'avg_2024' ? '2024' : '2025'} />
            <Bar dataKey="avg_2024" fill="#73726c" radius={[4, 4, 0, 0]} />
            <Bar dataKey="avg_2025" fill="#1D9E75" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="drift-table">
        {chartData.map(d => (
          <div key={d.day} className="drift-row">
            <span className="drift-day">{d.day}</span>
            <span className="drift-values">{d.avg_2024.toLocaleString()} → {d.avg_2025.toLocaleString()}</span>
            <span className={`drift-pct ${d.change_pct > 0 ? 'up' : 'down'}`}>
              {d.change_pct > 0 ? '+' : ''}{d.change_pct}%
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
