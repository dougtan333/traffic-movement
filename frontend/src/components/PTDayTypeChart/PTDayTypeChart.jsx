/**
 * PTDayTypeChart — grouped bar chart comparing PT patronage
 * across Normal Weekday, School Holiday Weekday, and Weekend.
 * Shows how day type affects patronage by mode.
 */
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis,
  CartesianGrid, Tooltip, Legend,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import './PTDayTypeChart.css';

const DAY_TYPE_COLORS = {
  'Normal Weekday': '#1B3A5C',
  'School Holiday Weekday': '#E9C46A',
  'Weekend': '#2A9D8F',
};

const MODE_LABELS = {
  MetroTrain: 'Train',
  Tram: 'Tram',
  MetroBus: 'Bus',
  RegionalTrain: 'Regional',
  RegionalBus: 'Reg. Bus',
};

export default function PTDayTypeChart() {
  const { data, loading, error } = useTrafficData('/api/transport/pt-daytype', { year: 2025 });

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data) return null;

  const dayTypes = Object.keys(data.data);
  const modes = ['MetroTrain', 'Tram', 'MetroBus', 'RegionalTrain', 'RegionalBus'];

  // Reshape: one row per mode, columns per day type
  const chartData = modes.map(mode => {
    const row = { mode: MODE_LABELS[mode] || mode };
    dayTypes.forEach(dt => {
      row[dt] = data.data[dt]?.[mode] || 0;
    });
    return row;
  });

  const formatK = (v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v;

  return (
    <div className="pt-daytype">
      <div className="chart-container">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
            <XAxis dataKey="mode" tick={{ fontSize: 11 }} />
            <YAxis tickFormatter={formatK} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => [v.toLocaleString(), '']} />
            <Legend />
            {dayTypes.map(dt => (
              <Bar
                key={dt}
                dataKey={dt}
                name={dt}
                fill={DAY_TYPE_COLORS[dt] || '#999'}
                radius={[3, 3, 0, 0]}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
