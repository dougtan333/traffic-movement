/**
 * HourlyProfileChart — weekday hourly profile with year overlays.
 * Shows how the commuter curve has changed across years. Victoria only.
 */
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import { YEAR_COLORS } from '../../constants';
import './HourlyProfileChart.css';

const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => {
  const h = i % 12 || 12;
  return `${h}${i < 12 ? 'am' : 'pm'}`;
});

export default function HourlyProfileChart() {
  const { data, loading, error } = useTrafficData('/api/traffic/hourly-profile-multi', {
    years: '2024,2025,2026',
  });

  if (loading) return <div className="chart-loading">Loading hourly profile…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data) return null;

  const yearKeys = Object.keys(data.data);
  const chartData = Array.from({ length: 24 }, (_, i) => {
    const point = { hour: i, label: HOUR_LABELS[i] };
    yearKeys.forEach(y => {
      const yearData = data.data[y];
      point[y] = yearData?.[i]?.avg_count || 0;
    });
    return point;
  });

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v, name) => [v.toLocaleString(), name]} />
          <Legend />
          {yearKeys.map(y => (
            <Line
              key={y}
              type="monotone"
              dataKey={y}
              stroke={YEAR_COLORS[y] || '#888'}
              strokeWidth={y === yearKeys[yearKeys.length - 1] ? 2.5 : 1.5}
              strokeDasharray={y === yearKeys[yearKeys.length - 1] ? undefined : '5 3'}
              dot={false}
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
