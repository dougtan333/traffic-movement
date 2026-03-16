/**
 * WeeklyTrendChart — weekday average vehicles per station, weekly.
 * Annotates: fuel crisis onset, school holiday periods, major events.
 *
 * @param {{ city: string }} props
 */
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, ReferenceArea,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import { useCalendarEvents } from '../../hooks/useCalendarEvents';
import { CITY_COLORS, CRISIS_DATE } from '../../constants';
import './WeeklyTrendChart.css';

export default function WeeklyTrendChart({ city }) {
  const { data, loading, error } = useTrafficData('/api/traffic/weekly-trend', {
    city, weeks: 52,
  });
  const { events: calData } = useCalendarEvents(city);

  if (loading) return <div className="chart-loading">Loading weekly trend…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  const chartData = data.data.map(d => ({
    ...d,
    label: new Date(d.week).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
  }));

  // Find the chart label for a given date (match to nearest week)
  const dateToLabel = (dateStr) => {
    const target = new Date(dateStr);
    let closest = chartData[0];
    let minDist = Infinity;
    for (const d of chartData) {
      const dist = Math.abs(new Date(d.week) - target);
      if (dist < minDist) { minDist = dist; closest = d; }
    }
    return closest?.label;
  };

  return (
    <div className="chart-container">
      <div className="chart-legend">
        <span className="legend-item"><span className="legend-swatch" style={{ background: CITY_COLORS[city] }} />Weekly avg</span>
        <span className="legend-item"><span className="legend-swatch school-swatch" />School holidays</span>
        <span className="legend-item"><span className="legend-line crisis-line" />Iran conflict</span>
      </div>
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

          {/* School holiday shading */}
          {(calData?.school_holidays || []).map((period, i) => {
            const x1 = dateToLabel(period.start);
            const x2 = dateToLabel(period.end);
            if (!x1 || !x2) return null;
            return (
              <ReferenceArea
                key={`school-${i}`}
                x1={x1} x2={x2}
                fill="#e9c46a" fillOpacity={0.15}
                stroke="none"
              />
            );
          })}

          {/* Iran conflict marker */}
          <ReferenceLine
            x={chartData.find(d => d.week >= CRISIS_DATE)?.label}
            stroke="#c4342d"
            strokeDasharray="5 3"
            strokeWidth={1.5}
            label={{ value: 'Iran conflict', position: 'top', fontSize: 10, fill: '#c4342d' }}
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
