/**
 * WeeklyTrendChart — weekday average vehicles per station, weekly.
 * Annotates: fuel crisis onset, school holiday periods, major events.
 * Victoria only.
 *
 * Annotations use data-driven approach (fields baked into chartData)
 * rather than Recharts ReferenceArea/ReferenceLine, which broke in v3.
 */
import {
  ResponsiveContainer, ComposedChart, Line, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, Customized,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import { useCalendarEvents } from '../../hooks/useCalendarEvents';
import { CITY_COLORS, CRISIS_DATE } from '../../constants';
import './WeeklyTrendChart.css';

/** Check whether a week date falls inside any school holiday period */
function isSchoolHoliday(weekStr, periods) {
  if (!periods?.length) return false;
  const d = new Date(weekStr);
  for (const p of periods) {
    // Extend window by 6 days so a week starting near a holiday edge is included
    const start = new Date(p.start);
    const end = new Date(p.end);
    end.setDate(end.getDate() + 6);
    if (d >= start && d <= end) return true;
  }
  return false;
}

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

  // Track which YoY keys get matched so we can project the remainder
  const matchedYoyKeys = new Set();

  const chartData = data.data.map(d => {
    const weekDate = new Date(d.week);
    let yoyVal = null;
    for (const [shiftedStr, val] of Object.entries(yoyLookup)) {
      const shiftedDate = new Date(shiftedStr);
      if (Math.abs(weekDate - shiftedDate) <= 7 * 86400000) {
        yoyVal = val;
        matchedYoyKeys.add(shiftedStr);
        break;
      }
    }
    return {
      ...d,
      label: weekDate.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
      yoy: yoyVal,
    };
  });

  // Project unmatched YoY weeks forward (next ~2 weeks beyond current data)
  const latestWeek = data.data.length ? new Date(data.data[data.data.length - 1].week) : null;
  if (latestWeek) {
    const projectionLimit = new Date(latestWeek);
    projectionLimit.setDate(projectionLimit.getDate() + 21);
    const projections = Object.entries(yoyLookup)
      .filter(([key]) => !matchedYoyKeys.has(key))
      .map(([shiftedStr, val]) => ({ date: new Date(shiftedStr), val }))
      .filter(p => p.date > latestWeek && p.date <= projectionLimit)
      .sort((a, b) => a.date - b.date);
    for (const p of projections) {
      chartData.push({
        week: p.date.toISOString().slice(0, 10),
        avg_per_station: null,
        label: p.date.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
        yoy: p.val,
      });
    }
  }

  // Compute Y-axis range for school holiday band height
  const allVals = chartData.flatMap(d => [d.avg_per_station, d.yoy].filter(v => v != null));
  const yMax = Math.max(...allVals) + 1000;
  const yMin = Math.min(...allVals) - 2000;

  // Bake school holiday annotation into each data point
  const schoolPeriods = calData?.school_holidays || [];
  for (const d of chartData) {
    d.schoolHol = isSchoolHoliday(d.week, schoolPeriods) ? yMax : null;
  }
  // Find the crisis onset index for the Customized renderer
  const crisisIdx = chartData.findIndex(d => d.week >= CRISIS_DATE);

  return (
    <div className="chart-container">
      <div className="chart-legend">
        <span className="legend-item"><span className="legend-swatch" style={{ background: CITY_COLORS.melbourne }} />Avg daily vehicles/station</span>
        <span className="legend-item"><span className="legend-swatch" style={{ background: CITY_COLORS.melbourne, opacity: 0.25 }} />Prior year</span>
        <span className="legend-item"><span className="legend-swatch school-swatch" />School holidays</span>
        <span className="legend-item"><span className="legend-line crisis-line" />Iran conflict</span>
      </div>
      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="label" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
          <YAxis
            label={{ value: 'Vehicles/day/station', angle: -90, position: 'insideLeft', offset: 0, style: { fontSize: 11, fill: '#888' } }}
            tick={{ fontSize: 11 }}
            tickFormatter={v => v >= 1000 ? `${(v/1000).toFixed(0)}k` : v}
            domain={[yMin, yMax]}
          />
          <Tooltip
            formatter={(value, name) => {
              if (value == null) return [null, null];
              if (name === 'schoolHol' || name === 'crisisLine') return [null, null];
              const label = name === 'yoy' ? 'Prior year' : 'Vehicles/day/station';
              return [value.toLocaleString(), label];
            }}
            labelFormatter={(label) => `Week of ${label}`}
          />

          {/* School holiday shading — Area fills full chart height during holiday weeks */}
          <Area
            type="step"
            dataKey="schoolHol"
            fill="#e9c46a"
            fillOpacity={0.15}
            stroke="none"
            isAnimationActive={false}
            connectNulls={false}
            baseValue={yMin}
          />

          {/* Iran conflict marker — rendered via Customized to access chart coordinates */}

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

          {/* Iran conflict — vertical dashed line via Customized */}
          <Customized component={(props) => {
            if (crisisIdx < 0) return null;
            const { xAxisMap, yAxisMap, offset } = props;
            const xAxis = xAxisMap && Object.values(xAxisMap)[0];
            const yAxis = yAxisMap && Object.values(yAxisMap)[0];
            if (!xAxis?.scale || !yAxis?.scale) return null;
            const cx = xAxis.scale(crisisIdx) + (xAxis.bandSize || 0) / 2;
            const y1 = offset?.top ?? 5;
            const y2 = (offset?.top ?? 5) + (offset?.height ?? 300);
            return (
              <g>
                <line x1={cx} x2={cx} y1={y1} y2={y2}
                  stroke="#c4342d" strokeWidth={1.5} strokeDasharray="5 3" />
                <text x={cx + 4} y={y1 + 10} fontSize={10} fill="#c4342d">
                  Iran conflict
                </text>
              </g>
            );
          }} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
