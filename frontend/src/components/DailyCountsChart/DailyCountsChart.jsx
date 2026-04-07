/**
 * DailyCountsChart — daily traffic bar chart with weekday/weekend colouring.
 * Highlights post-crisis days in red tones. Victoria only.
 */
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Cell,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import { CITY_COLORS, CRISIS_DATE } from '../../constants';
import './DailyCountsChart.css';

function rollingDates(weeksBack = 8) {
  const to = new Date();
  const from = new Date(to);
  from.setDate(from.getDate() - weeksBack * 7);
  return {
    from: from.toISOString().slice(0, 10),
    to: to.toISOString().slice(0, 10),
  };
}

export default function DailyCountsChart({ dateFrom, dateTo }) {
  const defaults = rollingDates(8);
  const from = dateFrom || defaults.from;
  const to = dateTo || defaults.to;
  const { data, loading, error } = useTrafficData('/api/traffic/daily-counts', {
    date_from: from, date_to: to,
  });

  if (loading) return <div className="chart-loading">Loading daily counts…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  const chartData = data.data.map(d => ({
    ...d,
    label: new Date(d.day).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
    isCrisis: d.day >= CRISIS_DATE,
  }));

  const cityColor = CITY_COLORS.melbourne;

  const getBarColor = (entry) => {
    if (entry.isCrisis) {
      return entry.is_weekday && !entry.is_holiday ? '#E24B4A' : 'rgba(226,75,74,0.3)';
    }
    return entry.is_weekday && !entry.is_holiday ? cityColor : `${cityColor}44`;
  };

  return (
    <div className="chart-container">
      <div className="chart-legend">
        <span className="legend-item"><span className="legend-swatch" style={{ background: cityColor }} />Weekday</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: `${cityColor}44` }} />Weekend/holiday</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: '#E24B4A' }} />Post-crisis weekday</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: 'rgba(226,75,74,0.3)' }} />Post-crisis weekend</span>
      </div>
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={2} angle={-45} textAnchor="end" height={50} />
          <YAxis
            label={{ value: 'Vehicles/day/station', angle: -90, position: 'insideLeft', offset: 0, style: { fontSize: 11, fill: '#888' } }}
            tick={{ fontSize: 11 }}
            tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v}
          />
          <Tooltip
            formatter={(value) => [value.toLocaleString(), 'Vehicles/day/station']}
            labelFormatter={(_, payload) => {
              if (!payload?.[0]) return '';
              const d = payload[0].payload;
              const dow = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d.day_of_week] || '';
              return `${dow} ${d.day}${d.is_holiday ? ' (holiday)' : ''}`;
            }}
          />
          <Bar dataKey="avg_per_station" radius={[2, 2, 0, 0]}>
            {chartData.map((entry, i) => (
              <Cell key={i} fill={getBarColor(entry)} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
