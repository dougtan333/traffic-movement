/**
 * StationProfile — hourly profile for a single selected station.
 * Appears when a station is clicked on the map.
 * Also shows nearest fuel station prices.
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

/** Preferred fuel types to display, in order */
const DISPLAY_FUELS = ['U91', 'E10', 'P95', 'P98', 'DSL', 'LPG'];

export default function StationProfile({ stationId, onClose }) {
  const { data, loading, error } = useTrafficData('/api/traffic/station-profile', {
    station_id: stationId, year: 2025,
  });

  // Fetch nearby fuel once we have station coords
  const stationLat = data?.station?.lat;
  const stationLon = data?.station?.lon;
  const { data: fuelData } = useTrafficData(
    stationLat ? '/api/fuel/nearby' : null,
    stationLat ? { lat: stationLat, lon: stationLon, limit: 3 } : {},
  );

  if (loading) return <div className="station-profile"><div className="chart-loading">Loading…</div></div>;
  if (error) return <div className="station-profile"><div className="chart-error">{error}</div></div>;
  if (!data?.hourly?.length) return null;

  const { station, hourly } = data;
  const color = CITY_COLORS.melbourne;
  const peak = Math.max(...hourly.map(h => h.avg_count));
  const peakHour = hourly.find(h => h.avg_count === peak);

  const chartData = hourly.map(h => ({
    ...h,
    label: HOUR_LABELS[h.hour],
  }));

  const nearbyStations = fuelData?.stations || [];

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

      {nearbyStations.length > 0 && (
        <div className="nearby-fuel">
          <h5 className="nearby-fuel-title">Nearest fuel stations</h5>
          {nearbyStations.map((fs) => (
            <div key={fs.station_id} className="fuel-station-card">
              <div className="fuel-station-header">
                <span className="fuel-station-name">{fs.brand} — {fs.suburb}</span>
                <span className="fuel-station-dist">{fs.dist_km} km</span>
              </div>
              <div className="fuel-station-prices">
                {DISPLAY_FUELS
                  .filter(ft => fs.prices[ft])
                  .map(ft => (
                    <span key={ft} className="fuel-price-tag">
                      {ft} <strong>{fs.prices[ft].toFixed(1)}¢</strong>
                    </span>
                  ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
