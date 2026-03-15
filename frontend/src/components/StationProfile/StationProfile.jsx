/**
 * StationProfile — hourly profile for a single selected station.
 * Appears when a station is clicked on the map.
 *
 * @param {{ stationId: string, onClose: () => void }} props
 */
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import { CITY_COLORS } from '../../constants';
import './StationProfile.css';

const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => {
  const h = i % 12 || 12;
  return `${h}${i < 12 ? 'am' : 'pm'}`;
});

export default function StationProfile({ stationId, onClose }) {
  const { data, loading, error } = useTrafficData('/api/traffic/station-profile', {
    station_id: stationId, year: 2025,
  });

  if (loading) return <div className="station-profile"><div className="chart-loading">Loading…</div></div>;
  if (error) return <div className="station-profile"><div className="chart-error">{error}</div></div>;
  if (!data?.hourly?.length) return null;

  const { station, hourly } = data;
  const city = station.id.startsWith('VIC') ? 'melbourne' : 'sydney';
  const color = CITY_COLORS[city];
  const peak = Math.max(...hourly.map(h => h.avg_count));
  const peakHour = hourly.find(h => h.avg_count === peak);

  const chartData = hourly.map(h => ({
    ...h,
    label: HOUR_LABELS[h.hour],
  }));

  return (
    <div className="station-profile">
      <div className="station-profile-header">
        <div>
          <h4 className="station-name">{station.road_name}</h4>
          <span className="station-meta">
            {station.suburb && `${station.suburb} · `}{station.road_type} · Peak: {peak.toLocaleString()}/hr at {HOUR_LABELS[peakHour.hour]}
          </span>
        </div>
        <button className="station-close" onClick={onClose}>×</button>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <AreaChart data={chartData} margin={{ top: 5, right: 10, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#eee" />
          <XAxis dataKey="label" tick={{ fontSize: 10 }} />
          <YAxis tick={{ fontSize: 10 }} />
          <Tooltip formatter={(v) => [v.toLocaleString(), 'Avg/hr']} />
          <Area
            type="monotone"
            dataKey="avg_count"
            stroke={color}
            fill={color}
            fillOpacity={0.15}
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
