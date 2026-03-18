/**
 * DayOfWeekChart — bar chart showing Mon–Sun traffic averages.
 * Business hours only (7am–6pm) to capture commuter signal. Victoria only.
 */
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Cell,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import { CITY_COLORS } from '../../constants';

export default function DayOfWeekChart() {
  const { data, loading, error } = useTrafficData('/api/traffic/day-of-week', {
    year: 2025,
  });

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  const cityColor = CITY_COLORS.melbourne;

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data.data} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
          <XAxis dataKey="day" tick={{ fontSize: 12 }} />
          <YAxis tick={{ fontSize: 11 }} domain={[0, 'dataMax + 100']} />
          <Tooltip formatter={(v) => [v.toLocaleString(), 'Avg/hr']} />
          <Bar dataKey="avg_count" radius={[4, 4, 0, 0]}>
            {data.data.map((entry, i) => (
              <Cell key={i} fill={entry.day_num <= 5 ? cityColor : `${cityColor}66`} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
