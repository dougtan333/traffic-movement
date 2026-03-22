/**
 * HourlyProfileChart — hourly profile with year overlays + TIRTL speed.
 * Toggleable between weekday, Saturday, and Sunday.
 * Left axis: vehicle counts per 15-min interval per station (SCATS, multi-year).
 * Right axis: average freeway speed in km/h (TIRTL sensors, matched to day type).
 * Victoria only.
 */
import { useState } from 'react';
import {
  ResponsiveContainer, ComposedChart, Line, Area, XAxis, YAxis,
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

const SPEED_COLOR = '#c4342d';

export default function HourlyProfileChart() {
  const [dayType, setDayType] = useState('weekday');
  const { data, loading, error } = useTrafficData('/api/traffic/hourly-profile-multi', {
    years: '2024,2025,2026',
    day_type: dayType,
  });
  const { data: speedData } = useTrafficData('/api/tirtl/speed-by-hour', {});

  if (loading) return <div className="chart-loading">Loading hourly profile…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data) return null;

  // Map TIRTL speed by hour for the matching day type
  const speedByHour = {};
  if (speedData?.data) {
    const tirtlDayType = dayType === 'weekday' ? 'weekday' : 'weekend';
    speedData.data
      .filter(d => d.day_type === tirtlDayType)
      .forEach(d => { speedByHour[d.hour] = d.avg_speed; });
  }

  const yearKeys = Object.keys(data.data);
  const chartData = Array.from({ length: 24 }, (_, i) => {
    const point = { hour: i, label: HOUR_LABELS[i] };
    yearKeys.forEach(y => {
      const yearData = data.data[y];
      point[y] = yearData?.[i]?.avg_count || 0;
    });
    point.speed = speedByHour[i] ?? null;
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
        <ComposedChart data={chartData} margin={{ top: 5, right: 50, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} />
          <YAxis
            yAxisId="left"
            tick={{ fontSize: 11 }}
            label={{ value: 'Vehicles/15 min/station', angle: -90, position: 'insideLeft', offset: 0, style: { fontSize: 11, fill: '#888' } }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            domain={[0, 120]}
            tick={{ fontSize: 11, fill: SPEED_COLOR }}
            label={{ value: 'Freeway speed (km/h)', angle: 90, position: 'insideRight', offset: 0, style: { fontSize: 11, fill: SPEED_COLOR } }}
          />
          <Tooltip
            formatter={(v, name) => {
              if (name === 'speed') return v != null ? [`${v} km/h`, 'Freeway speed'] : [null, null];
              return [v.toLocaleString(), `${name} avg`];
            }}
          />
          <Legend
            formatter={(v) => v === 'speed' ? 'Freeway speed (TIRTL)' : `${v} avg`}
          />

          {/* Speed as shaded area on right axis */}
          <Area
            yAxisId="right"
            type="monotone"
            dataKey="speed"
            stroke={SPEED_COLOR}
            fill={SPEED_COLOR}
            fillOpacity={0.04}
            strokeWidth={1.5}
            strokeDasharray="4 2"
            dot={false}
            connectNulls
          />

          {/* Volume lines on left axis */}
          {yearKeys.map(y => (
            <Line
              key={y}
              yAxisId="left"
              type="monotone"
              dataKey={y}
              stroke={YEAR_COLORS[y] || '#888'}
              strokeWidth={y === yearKeys[yearKeys.length - 1] ? 2.5 : 1.5}
              strokeDasharray={y === yearKeys[yearKeys.length - 1] ? undefined : '5 3'}
              dot={false}
            />
          ))}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
