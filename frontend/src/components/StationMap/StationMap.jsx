/**
 * StationMap — interactive map showing VIC station locations.
 * Click a station to see its hourly profile.
 * Uses Leaflet + OpenStreetMap tiles (free, no API key).
 */
import { MapContainer, TileLayer, CircleMarker, Popup } from 'react-leaflet';
import { useTrafficData } from '../../hooks/useTrafficData';
import { CITY_COLORS } from '../../constants';
import 'leaflet/dist/leaflet.css';
import './StationMap.css';

const MEL_CENTER = { lat: -37.81, lon: 144.96, zoom: 11 };

export default function StationMap({ onSelectStation, selectedStation }) {
  const { data, loading, error } = useTrafficData('/api/stations/');

  if (loading) return <div className="chart-loading">Loading stations…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.stations?.length) return null;

  const color = CITY_COLORS.melbourne;

  return (
    <div className="station-map-container">
      <MapContainer
        center={[MEL_CENTER.lat, MEL_CENTER.lon]}
        zoom={MEL_CENTER.zoom}
        className="station-map"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {data.stations.map(s => (
          <CircleMarker
            key={s.station_id}
            center={[s.lat, s.lon]}
            radius={selectedStation === s.station_id ? 8 : 5}
            pathOptions={{
              color: selectedStation === s.station_id ? '#E24B4A' : color,
              fillColor: selectedStation === s.station_id ? '#E24B4A' : color,
              fillOpacity: selectedStation === s.station_id ? 0.9 : 0.6,
              weight: selectedStation === s.station_id ? 2 : 1,
            }}
            eventHandlers={{
              click: () => onSelectStation(s.station_id),
            }}
          >
            <Popup>
              <strong>{s.road_name}</strong>
              {s.suburb && <br />}{s.suburb}
              <br /><span style={{ fontSize: '0.75rem', color: '#666' }}>{s.road_type}</span>
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
