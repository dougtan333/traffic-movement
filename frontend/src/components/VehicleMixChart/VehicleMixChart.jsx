/**
 * VehicleMixChart — daily vehicle classification from TIRTL sensors.
 * Stacked bar chart showing cars vs trucks vs buses over time.
 */
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';

const CATEGORY_COLORS = {
  Cars: '#2A9D8F',
  'Cars+trailer': '#8ecae6',
  'Rigid trucks': '#E9C46A',
  'Articulated/B-double': '#F4A261',
  Buses: '#6D2E46',
  Other: '#d1d5db',
};

const formatM = (v) => `${(v / 1_000_000).toFixed(1)}M`;

export default function VehicleMixChart() {
  const { data, loading, error } = useTrafficData('/api/tirtl/vehicle-mix', {});

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  const chartData = data.data
    .filter(d => d.date >= '2026-02-01')
    .map(d => ({
    ...d,
    label: new Date(d.date).toLocaleDateString('en-AU', { day: 'numeric', month: 'short', weekday: 'short' }),
  }));

  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height={280}>
        <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 10 }} />
          <YAxis tickFormatter={formatM} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v) => [v.toLocaleString(), '']} />
          <Legend />
          <Bar dataKey="Cars" stackId="1" fill={CATEGORY_COLORS.Cars} />
          <Bar dataKey="Rigid trucks" stackId="1" fill={CATEGORY_COLORS['Rigid trucks']} />
          <Bar dataKey="Articulated/B-double" stackId="1" fill={CATEGORY_COLORS['Articulated/B-double']} />
          <Bar dataKey="Cars+trailer" stackId="1" fill={CATEGORY_COLORS['Cars+trailer']} />
          <Bar dataKey="Other" stackId="1" fill={CATEGORY_COLORS.Other} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
