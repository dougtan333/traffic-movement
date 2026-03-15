/**
 * SchoolHolidayChart — paired bar chart comparing school holiday
 * vs term-time traffic, with summary metric card.
 *
 * @param {{ city: string }} props
 */
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import { CITY_COLORS } from '../../constants';
import './SchoolHolidayChart.css';

export default function SchoolHolidayChart({ city }) {
  const { data, loading, error } = useTrafficData('/api/traffic/school-holiday-effect', { city });

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.monthly?.length) return null;

  const { summary, monthly } = data;
  const color = CITY_COLORS[city];

  // Filter to months that have both term and holiday data
  const chartData = monthly
    .filter(m => m.term != null || m.holiday != null)
    .map(m => ({
      ...m,
      label: new Date(m.month).toLocaleDateString('en-AU', { month: 'short' }),
    }));

  return (
    <div className="school-holiday-panel">
      <div className="school-holiday-summary">
        <div className="sh-metric">
          <span className="sh-label">Term-time avg</span>
          <span className="sh-value">{summary.term_avg.toLocaleString()}</span>
        </div>
        <div className="sh-metric">
          <span className="sh-label">Holiday avg</span>
          <span className="sh-value">{summary.holiday_avg.toLocaleString()}</span>
        </div>
        <div className="sh-metric">
          <span className="sh-label">Holiday effect</span>
          <span className="sh-value sh-effect">{summary.effect_pct}%</span>
        </div>
      </div>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={240}>
          <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 11 }} />
            <YAxis tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => v ? [v.toLocaleString(), ''] : ['No data', '']} />
            <Legend />
            <Bar dataKey="term" name="Term time" fill={color} radius={[3, 3, 0, 0]} />
            <Bar dataKey="holiday" name="School holiday" fill={`${color}66`} radius={[3, 3, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
