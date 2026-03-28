/**
 * FuelByPostcode — postcode dropdown + ranked station table.
 * User selects their postcode, sees cheapest to most expensive stations.
 */
import { useState } from 'react';
import { useTrafficData } from '../../hooks/useTrafficData';
import './FuelByPostcode.css';

export default function FuelByPostcode() {
  const [postcode, setPostcode] = useState('3806');
  const [fuelType, setFuelType] = useState('U91');

  const { data: postcodeList } = useTrafficData('/api/fuel/postcodes');
  const { data, loading, error } = useTrafficData('/api/fuel/by-postcode', { postcode, fuel_type: fuelType });

  const fuelTypes = ['U91', 'P95', 'P98', 'DSL', 'E10', 'LPG'];

  return (
    <div className="fuel-postcode">
      <div className="fuel-postcode-controls">
        <label>
          Postcode
          <select value={postcode} onChange={e => setPostcode(e.target.value)}>
            {(postcodeList?.postcodes || []).map(p => (
              <option key={p.postcode} value={p.postcode}>
                {p.postcode} — {p.suburb || 'Unknown'} ({p.stations})
              </option>
            ))}
          </select>
        </label>
        <label>
          Fuel type
          <select value={fuelType} onChange={e => setFuelType(e.target.value)}>
            {fuelTypes.map(ft => <option key={ft} value={ft}>{ft}</option>)}
          </select>
        </label>
      </div>

      {loading && <div className="chart-loading">Loading…</div>}
      {error && <div className="chart-error">Error: {error}</div>}

      {data?.stations?.length > 0 && (
        <div className="fuel-postcode-results">
          <div className="fuel-postcode-summary">
            <span className="fuel-cheapest">{data.stations[0].price_cpl}c</span>
            <span className="fuel-dash">→</span>
            <span className="fuel-expensive">{data.stations[data.stations.length - 1].price_cpl}c</span>
            <span className="fuel-count">{data.stations.length} stations in {postcode}</span>
            {data.date && (
              <span className="fuel-date">
                {new Date(data.date + 'T00:00:00').toLocaleDateString('en-AU', {
                  weekday: 'short', day: 'numeric', month: 'short', year: 'numeric'
                })}
              </span>
            )}
          </div>

          <div className="table-scroll">
          <table className="fuel-table">
            <thead>
              <tr>
                <th>Station</th>
                <th>Brand</th>
                <th className="fuel-price-col">Price</th>
              </tr>
            </thead>
            <tbody>
              {data.stations.map((s, i) => (
                <tr key={i} className={i === 0 ? 'fuel-cheapest-row' : ''}>
                  <td>{s.name}</td>
                  <td>{s.brand}</td>
                  <td className="fuel-price-col">{s.price_cpl}c</td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {data?.stations?.length === 0 && !loading && (
        <div className="fuel-postcode-empty">No stations found in {postcode} for {fuelType}</div>
      )}
    </div>
  );
}
