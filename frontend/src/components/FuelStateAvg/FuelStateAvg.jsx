/**
 * FuelStateAvg — VIC state average fuel price summary cards.
 * Shows current average price per fuel type with station counts.
 */
import { useTrafficData } from '../../hooks/useTrafficData';
import './FuelStateAvg.css';

const FUEL_LABELS = {
  U91: 'Unleaded 91', P95: 'Premium 95', P98: 'Premium 98',
  DSL: 'Diesel', PDSL: 'Premium Diesel', E10: 'Ethanol E10',
  LPG: 'LPG', E85: 'Ethanol E85',
};
const PRIMARY_TYPES = ['U91', 'P95', 'P98', 'DSL', 'E10', 'LPG'];

export default function FuelStateAvg() {
  const { data, loading, error } = useTrafficData('/api/fuel/state-average');

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  // Get latest date's data only, sorted cheapest to most expensive
  const latestDate = data.data[data.data.length - 1]?.date;
  const latest = data.data
    .filter(d => d.date === latestDate && PRIMARY_TYPES.includes(d.fuel_type))
    .sort((a, b) => a.avg_price - b.avg_price);

  return (
    <div className="fuel-avg">
      <div className="fuel-avg-date">
        Prices as of {new Date(latestDate + 'T00:00:00').toLocaleDateString('en-AU', {
          weekday: 'long', day: 'numeric', month: 'long', year: 'numeric'
        })}
      </div>
      <div className="fuel-avg-cards">
        {latest.map(d => (
          <div key={d.fuel_type} className="fuel-avg-card">
            <div className="fuel-avg-type">{FUEL_LABELS[d.fuel_type] || d.fuel_type}</div>
            <div className="fuel-avg-price">{d.avg_price.toFixed(1)}<span className="fuel-avg-unit">c/l</span></div>
            <div className="fuel-avg-range">{d.min_price.toFixed(1)}c – {d.max_price.toFixed(1)}c</div>
            <div className="fuel-avg-stations">{d.stations} stations</div>
          </div>
        ))}
      </div>
    </div>
  );
}
