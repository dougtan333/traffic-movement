/**
 * WeeklyTrendChart — weekday average vehicles per station, weekly.
 * Annotates: fuel crisis onset, school holiday periods, major events.
 * Victoria only.
 */
import {
  ResponsiveContainer, LineChart, Line, XAxis, YAxis,
  CartesianGrid, Tooltip, ReferenceLine, ReferenceArea,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import { useCalendarEvents } from '../../hooks/useCalendarEvents';
import { CITY_COLORS, CRISIS_DATE } from '../../constants';
import './WeeklyTrendChart.css';

export default function WeeklyTrendChart() {
  const { data, loading, error } = useTrafficData('/api/traffic/weekly-trend', {
    weeks: 52,
  });
  const { events: calData } = useCalendarEvents();

  if (loading) return <div className="chart-loading">Loading weekly trend…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  // Build a lookup of YoY data: shift each prior-year week forward 1 year,
  // then match to the nearest current-year week
  const yoyLookup = {};
  if (data.yoy_data?.length) {
    for (const d of data.yoy_data) {
      const shifted = new Date(d.week);
      shifted.setFullYear(shifted.getFullYear() + 1);
      yoyLookup[shifted.toISOString().slice(0, 10)] = d.avg_per_station;
    }
  }

  const chartData = data.data.map(d => {
    // Find closest YoY match (within 7 days of shifted date)
    const weekDate = new Date(d.week);
    let yoyVal = null;
    for (const [shiftedStr, val] of Object.entries(yoyLookup)) {
      const shiftedDate = new Date(shiftedStr);
      if (Math.abs(weekDate - shiftedDate) <= 7 * 86400000) {
        yoyVal = val;
        break;
      }
    }
    return {
      ...d,
      label: weekDate.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
      yoy: yoyVal,
    };
  });

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
        <span className="legend-item"><span className="legend-swatch" style={{ background: CITY_COLORS.melbourne }} />Avg daily vehicles/station</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: CITY_COLORS.melbourne, opacity: 0.25 }} />Prior year</span>
        <span className="legend-item"><span className="legend-swatch school-swatch" />School holidays</span>
        <span className="legend-item"><span className="legend-line crisis-line" />Iran conflict</span>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
          <YAxis
            label={{ value: 'Vehicles/day/station', angle: -90, position: 'insideLeft', offset: 0, style: { fontSize: 11, fill: '#888' } }}
            tick={{ fontSize: 11 }}
            tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v}
            domain={['dataMin - 2000', 'dataMax + 1000']}
          />
          <Tooltip
            formatter={(value, name) => {
              if (value == null) return [null, null];
              const label = name === 'yoy' ? 'Prior year' : 'Vehicles/day/station';
              return [value.toLocaleString(), label];
            }}
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

          {/* Prior year comparison — faint */}
          <Line
            type="monotone"
            dataKey="yoy"
            stroke={CITY_COLORS.melbourne}
            strokeWidth={1.5}
            strokeOpacity={0.25}
            dot={false}
            activeDot={false}
            connectNulls={false}
          />

          <Line
            type="monotone"
            dataKey="avg_per_station"
            stroke={CITY_COLORS.melbourne}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 4 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
