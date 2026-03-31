/**
 * FuelOutages — fuel supply outage tracker.
 *
 * Shows daily outage counts by fuel type across VIC stations,
 * filtering out structural non-sellers (stations that never stock
 * a given fuel type). Displays:
 *  - Summary cards per fuel type (outage count, %, avg price)
 *  - Time-series line chart of outage % by fuel type
 *
 * Data: GET /api/fuel/outage-summary (cards), GET /api/fuel/outages (trend)
 * State filter is ready for future expansion beyond VIC.
 */
import { useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import './FuelOutages.css';

const FUEL_LABELS = {
  U91: 'Unleaded 91', P95: 'Premium 95', P98: 'Premium 98',
  DSL: 'Diesel', E10: 'Ethanol E10', LPG: 'LPG',
};

const FUEL_COLOURS = {
  U91: '#2563eb', DSL: '#dc2626', P95: '#7c3aed',
  P98: '#0891b2', E10: '#059669', LPG: '#d97706',
};

const CHART_TYPES = ['U91', 'DSL', 'P95', 'LPG'];

export default function FuelOutages() {
  const [state] = useState('VIC');
  const { data: summary, loading: loadSum } = useTrafficData(
    '/api/fuel/outage-summary', { state }
  );
  const { data: trend, loading: loadTrend } = useTrafficData(
    '/api/fuel/outages', { state }
  );

  if (loadSum || loadTrend) return <div className="chart-loading">Loading…</div>;

  // Pivot trend data: { date, U91: pct_out, DSL: pct_out, ... }
  const chartData = [];
  if (trend?.data) {
    const byDate = {};
    for (const r of trend.data) {
      if (!CHART_TYPES.includes(r.fuel_type)) continue;
      if (!byDate[r.date]) byDate[r.date] = { date: r.date };
      byDate[r.date][r.fuel_type] = r.pct_out;
      byDate[r.date][r.fuel_type + '_n'] = r.unavailable;
    }
    chartData.push(
      ...Object.values(byDate).sort((a, b) => a.date.localeCompare(b.date))
    );
  }

  const cards = summary?.fuel_types || [];
  const asOf = summary?.date
    ? new Date(summary.date + 'T00:00:00').toLocaleDateString('en-AU', {
        weekday: 'short', day: 'numeric', month: 'short',
      })
    : '';

  return (
    <div className="fuel-outages">
      <div className="fuel-outages-header">
        <span className="fuel-outages-state">{state}</span>
        {asOf && <span className="fuel-outages-date">as of {asOf}</span>}
      </div>

      {/* Summary cards — one per major fuel type */}
      <div className="fuel-outages-cards">
        {cards.map(c => {
          const severity = c.pct_out >= 5 ? 'severe' : c.pct_out >= 2 ? 'moderate' : 'normal';
          return (
            <div key={c.fuel_type} className={`fuel-outage-card fuel-outage-${severity}`}>
              <div className="fuel-outage-type">{FUEL_LABELS[c.fuel_type] || c.fuel_type}</div>
              <div className="fuel-outage-count">
                {c.unavailable}<span className="fuel-outage-label"> out</span>
              </div>
              <div className="fuel-outage-pct">{c.pct_out.toFixed(1)}% of {c.total_stations}</div>
              {c.avg_price_cpl && (
                <div className="fuel-outage-price">avg {c.avg_price_cpl.toFixed(1)}c/l</div>
              )}
            </div>
          );
        })}
      </div>

      {/* Trend chart — outage % by fuel type over time */}
      {chartData.length > 1 && (
        <div className="fuel-outages-chart">
          <ResponsiveContainer width="100%" height={260}>
            <LineChart data={chartData} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
              <XAxis
                dataKey="date"
                tickFormatter={v => {
                  const d = new Date(v + 'T00:00:00');
                  return d.toLocaleDateString('en-AU', { day: 'numeric', month: 'short' });
                }}
                tick={{ fontSize: 11 }}
              />
              <YAxis
                tick={{ fontSize: 11 }}
                tickFormatter={v => `${v}%`}
                domain={[0, 'auto']}
                label={{ value: '% unavailable', angle: -90, position: 'insideLeft', fontSize: 11, dx: -4 }}
              />
              <Tooltip
                formatter={(val, name) => [`${val.toFixed(1)}%`, FUEL_LABELS[name] || name]}
                labelFormatter={v => {
                  const d = new Date(v + 'T00:00:00');
                  return d.toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric', month: 'short' });
                }}
              />
              <Legend
                formatter={v => FUEL_LABELS[v] || v}
                wrapperStyle={{ fontSize: 11 }}
              />
              {CHART_TYPES.map(ft => (
                <Line
                  key={ft}
                  type="monotone"
                  dataKey={ft}
                  stroke={FUEL_COLOURS[ft]}
                  strokeWidth={2}
                  dot={{ r: 3 }}
                  connectNulls
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
      {chartData.length <= 1 && (
        <p className="fuel-outages-note">
          Outage trend chart requires 2+ days of data. Accumulating…
        </p>
      )}
    </div>
  );
}
