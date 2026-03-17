/**
 * TIRTLSpeedChart — hourly speed profile from TIRTL sensors.
 * Line chart showing weekday vs weekend speed patterns.
 */
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';

export default function TIRTLSpeedChart() {
  const { data, loading, error } = useTrafficData('/api/tirtl/speed-by-hour', {});

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  // Reshape: one row per hour with weekday + weekend columns
  const hours = {};
  data.data.forEach(d => {
    if (!hours[d.hour]) hours[d.hour] = { hour: `${d.hour}:00` };
    hours[d.hour][d.day_type] = d.avg_speed;
  });
  const chartData = Object.values(hours).sort((a, b) =>
    parseInt(a.hour) - parseInt(b.hour)
  );

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={240}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
          <XAxis dataKey="hour" tick={{ fontSize: 11 }} />
          <YAxis domain={[0, 'auto']} tick={{ fontSize: 11 }} label={{ value: 'km/h', angle: -90, position: 'insideLeft', fontSize: 11 }} />
          <Tooltip formatter={(v) => [`${v} km/h`, '']} />
          <Legend />
          <Line type="monotone" dataKey="weekday" name="Weekday" stroke="#1B3A5C" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="weekend" name="Weekend" stroke="#2A9D8F" strokeWidth={2} dot={false} strokeDasharray="6 3" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
