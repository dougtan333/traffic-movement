/**
 * DailyCountsChart — daily traffic bar chart with weekday/weekend colouring.
 * Highlights post-crisis days in red tones.
 *
 * @param {{ city: string, dateFrom: string, dateTo: string }} props
 */
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, Cell,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import { CITY_COLORS, CRISIS_DATE } from '../../constants';
import './DailyCountsChart.css';

export default function DailyCountsChart({ city, dateFrom = '2026-02-01', dateTo = '2026-03-31' }) {
  const { data, loading, error } = useTrafficData('/api/traffic/daily-counts', {
    city, date_from: dateFrom, date_to: dateTo,
  });

  if (loading) return <div className="chart-loading">Loading daily counts…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  const chartData = data.data.map(d => ({
    ...d,
    label: new Date(d.day).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
    isCrisis: d.day >= CRISIS_DATE,
  }));

  const cityColor = CITY_COLORS[city];

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
            tick={{ fontSize: 11 }}
            tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v}
          />
          <Tooltip
            formatter={(value) => [value.toLocaleString(), 'Avg/station']}
            labelFormatter={(_, payload) => {
              if (!payload?.[0]) return '';
              const d = payload[0].payload;
              const dow = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][d.day_of_week] || '';
              return `${dow} ${d.day}${d.is_holiday ? ' (holiday)' : ''}`;
            }}
          />
          <ReferenceLine
            x={chartData.find(d => d.day >= CRISIS_DATE)?.label}
            stroke="#E24B4A"
            strokeDasharray="5 3"
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
