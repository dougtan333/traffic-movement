/**
 * FuelTrafficOverlay — weekly traffic volume vs wholesale fuel price.
 * Dual Y-axis: left = traffic (vehicles/station), right = price (c/l).
 * The key question: does traffic drop when fuel prices spike?
 */
import {
  ComposedChart, Line, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import './FuelTrafficOverlay.css';

const CRISIS_DATE = '2026-03-02';

export default function FuelTrafficOverlay() {
  const { data, loading, error } = useTrafficData('/api/fuel/traffic-overlay');

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return <div className="chart-empty">No data</div>;

  const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

  // Last 52 weeks for readability
  const recent = data.data.slice(-52);
  const chartData = recent.map(d => {
    const dt = new Date(d.week + 'T00:00:00');
    return {
      week: d.week,
      label: dt.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
      dayLabel: `${DAYS[dt.getDay()]} ${dt.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' })}`,
      traffic: d.traffic_avg_per_station,
      tgp: d.tgp_cpl,
    };
  });

  return (
    <div className="traffic-overlay">
      <ResponsiveContainer width="100%" height={340}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: 'var(--color-text-secondary)' }}
            interval={Math.floor(chartData.length / 8)}
          />
          <YAxis
            yAxisId="traffic" orientation="left"
            tick={{ fontSize: 11, fill: 'var(--color-text-secondary)' }}
            label={{ value: 'vehicles/station', angle: -90, position: 'insideLeft', style: { fontSize: 10 } }}
            domain={['dataMin - 2000', 'dataMax + 1000']}
          />
          <YAxis
            yAxisId="price" orientation="right"
            tick={{ fontSize: 11, fill: 'var(--color-text-secondary)' }}
            label={{ value: 'c/litre', angle: 90, position: 'insideRight', style: { fontSize: 10 } }}
          />
          <Tooltip
            contentStyle={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', fontSize: 12 }}
            labelFormatter={(label, payload) => {
              const item = payload?.[0]?.payload;
              return item?.dayLabel || label;
            }}
            formatter={(val, name) => {
              if (name === 'Traffic') return [val?.toLocaleString(), name];
              return val ? [`${val.toFixed(1)}c`, name] : ['-', name];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine
            x={chartData.find(d => d.week >= CRISIS_DATE)?.label}
            yAxisId="traffic" stroke="#E24B4A" strokeDasharray="4 4"
            label={{ value: 'Crisis', position: 'top', fontSize: 10, fill: '#E24B4A' }}
          />
          <Bar
            yAxisId="traffic" dataKey="traffic" name="Traffic"
            fill="#185FA5" fillOpacity={0.6} radius={[2, 2, 0, 0]}
          />
          <Line
            yAxisId="price" type="monotone" dataKey="tgp" name="Melbourne TGP"
            stroke="#F4A261" strokeWidth={2.5} dot={false} connectNulls
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
