/**
 * FleetBreakdown — vehicle fleet composition by fuel type.
 * Horizontal distribution bar + detail table.
 * Victoria only — Q4 2025 registration snapshot.
 */
import { useTrafficData } from '../../hooks/useTrafficData';
import './FleetBreakdown.css';

const FUEL_COLORS = {
  Petrol: '#6b7280',
  Diesel: '#374151',
  Hybrid: '#2A9D8F',
  Electric: '#10b981',
  'LPG/Gas': '#E9C46A',
  Other: '#d1d5db',
};

export default function FleetBreakdown() {
  const { data, loading, error } = useTrafficData('/api/transport/fleet', {});

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.breakdown?.length) return null;

  return (
    <div className="fleet-panel">
      <div className="fleet-header">
        <span className="fleet-total">{data.total.toLocaleString()} registered vehicles</span>
        <span className="fleet-quarter">{data.quarter}</span>
      </div>

      <div className="fleet-bar">
        {data.breakdown.filter(b => b.pct >= 0.5).map(b => (
          <div
            key={b.fuel_type}
            className="fleet-segment"
            style={{ width: `${b.pct}%`, background: FUEL_COLORS[b.fuel_type] || '#999' }}
            title={`${b.fuel_type}: ${b.count.toLocaleString()} (${b.pct}%)`}
          >
            {b.pct >= 5 && <span>{b.pct}%</span>}
          </div>
        ))}
      </div>

      <div className="fleet-table">
        {data.breakdown.map(b => (
          <div key={b.fuel_type} className="fleet-row">
            <span className="fleet-dot" style={{ background: FUEL_COLORS[b.fuel_type] || '#999' }} />
            <span className="fleet-label">{b.fuel_type}</span>
            <span className="fleet-count">{b.count.toLocaleString()}</span>
            <span className="fleet-pct">{b.pct}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
