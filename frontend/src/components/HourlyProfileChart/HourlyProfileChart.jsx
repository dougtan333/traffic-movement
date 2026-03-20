/**
 * HourlyProfileChart — hourly profile with year overlays.
 * Toggleable between weekday, Saturday, and Sunday.
 * Shows how the traffic curve has changed across years. Victoria only.
 */
import { useState } from 'react';
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

const DAY_TYPES = [
  { value: 'weekday', label: 'Weekdays' },
  { value: 'saturday', label: 'Saturday' },
  { value: 'sunday', label: 'Sunday' },
];

export default function HourlyProfileChart() {
  const [dayType, setDayType] = useState('weekday');
  const { data, loading, error } = useTrafficData('/api/traffic/hourly-profile-multi', {
    years: '2024,2025,2026',
    day_type: dayType,
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
      <div className="day-type-toggle">
        {DAY_TYPES.map(dt => (
          <button
            key={dt.value}
            className={`toggle-btn ${dayType === dt.value ? 'active' : ''}`}
            onClick={() => setDayType(dt.value)}
          >
            {dt.label}
          </button>
        ))}
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis tick={{ fontSize: 11 }} label={{ value: 'Vehicles/15 min/station', angle: -90, position: 'insideLeft', offset: 0, style: { fontSize: 11, fill: '#888' } }} />
          <Tooltip formatter={(v, name) => [v.toLocaleString(), `${name} avg`]} />
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
