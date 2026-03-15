/**
 * WeeklyTrendChart — weekday average vehicles per station, weekly.
 * Annotates the fuel crisis onset and highlights post-crisis weeks.
 *
 * @param {{ city: string }} props
 */
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import { CITY_COLORS, CRISIS_DATE } from '../../constants';
import './WeeklyTrendChart.css';

export default function WeeklyTrendChart({ city }) {
  const { data, loading, error } = useTrafficData('/api/traffic/weekly-trend', {
    city,
    weeks: 52,
  });

  if (loading) return <div className="chart-loading">Loading weekly trend…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  const chartData = data.data.map(d => ({
    ...d,
    label: new Date(d.week).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
  }));

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
          <YAxis
            tick={{ fontSize: 11 }}
            tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v}
            domain={['dataMin - 2000', 'dataMax + 1000']}
          />
          <Tooltip
            formatter={(value) => [value.toLocaleString(), 'Avg/station']}
            labelFormatter={(label) => `Week of ${label}`}
          />
          <ReferenceLine
            x={chartData.find(d => d.week >= CRISIS_DATE)?.label}
            stroke="#E24B4A"
            strokeDasharray="5 3"
            label={{ value: 'Fuel crisis', position: 'top', fontSize: 11, fill: '#E24B4A' }}
          />
          <Line
            type="monotone"
            dataKey="avg_per_station"
            stroke={CITY_COLORS[city]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
