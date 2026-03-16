/**
 * PTPatronageChart — monthly public transport patronage trend.
 * Stacked area chart showing train, tram, bus patronage over time.
 * Victoria only — all data is Melbourne metro + regional VIC.
 */
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import './PTPatronageChart.css';

const MODE_COLORS = {
  metro_train: '#1B3A5C',
  metro_tram: '#2A9D8F',
  metro_bus: '#E9C46A',
  regional_train: '#F4A261',
  regional_bus: '#6D2E46',
};

const formatM = (v) => `${(v / 1_000_000).toFixed(1)}M`;

export default function PTPatronageChart() {
  const { data, loading, error } = useTrafficData('/api/transport/pt-monthly', {});

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  const chartData = data.data;

  return (
    <div className="pt-patronage">
      <div className="pt-summary">
        <span className="pt-latest">
          Latest: <strong>{chartData[chartData.length - 1].label}</strong> —{' '}
          {formatM(chartData[chartData.length - 1].total)} total trips
        </span>
      </div>
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={300}>
          <AreaChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={2} />
            <YAxis tickFormatter={formatM} tick={{ fontSize: 11 }} />
            <Tooltip
              formatter={(v, name) => [formatM(v), name.replace('metro_', 'Metro ').replace('regional_', 'Regional ')]}
              labelFormatter={(l) => l}
            />
            <Legend formatter={(v) => v.replace('metro_', 'Metro ').replace('regional_', 'Regional ')} />
            <Area type="monotone" dataKey="metro_train" stackId="1" stroke={MODE_COLORS.metro_train} fill={MODE_COLORS.metro_train} fillOpacity={0.8} />
            <Area type="monotone" dataKey="metro_tram" stackId="1" stroke={MODE_COLORS.metro_tram} fill={MODE_COLORS.metro_tram} fillOpacity={0.8} />
            <Area type="monotone" dataKey="metro_bus" stackId="1" stroke={MODE_COLORS.metro_bus} fill={MODE_COLORS.metro_bus} fillOpacity={0.8} />
            <Area type="monotone" dataKey="regional_train" stackId="1" stroke={MODE_COLORS.regional_train} fill={MODE_COLORS.regional_train} fillOpacity={0.8} />
            <Area type="monotone" dataKey="regional_bus" stackId="1" stroke={MODE_COLORS.regional_bus} fill={MODE_COLORS.regional_bus} fillOpacity={0.8} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
