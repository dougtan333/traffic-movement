/**
 * AviationPanel — Australian airport passenger trends, routes, and on-time performance.
 *
 * Data: BITRE monthly airport traffic (5 capital-city airports, 2024+).
 * Endpoints: /api/aviation/passengers, /routes/top, /otp/summary, /passengers/summary
 *
 * Layout:
 *   1. Summary cards — latest month pax per airport with YoY/MoM badges
 *   2. Passenger trend chart — multi-line monthly pax by airport (Recharts)
 *   3. Top routes table — ranked city pairs with load factors
 *   4. OTP leaderboard — on-time performance ranking (best and worst)
 */
import { useState } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, BarChart, Bar, Cell,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import './AviationPanel.css';

const COLOURS = {
  SYDNEY: '#2A9D8F',
  MELBOURNE: '#1B3A5C',
  BRISBANE: '#E9C46A',
  PERTH: '#F4A261',
  ADELAIDE: '#6D2E46',
};

const AIRPORTS = ['SYDNEY', 'MELBOURNE', 'BRISBANE', 'PERTH', 'ADELAIDE'];
const MONTH_NAMES = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

/** Format large numbers with K/M suffix */
function fmtPax(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M';
  if (n >= 1_000) return (n / 1_000).toFixed(0) + 'K';
  return n.toLocaleString();
}

/** Format a percentage with arrow */
function fmtPct(v) {
  if (v == null) return '';
  const arrow = v > 0 ? '↑' : v < 0 ? '↓' : '→';
  return `${arrow} ${Math.abs(v).toFixed(1)}%`;
}

export default function AviationPanel() {
  const { data: summaryData, loading: summaryLoading } = useTrafficData('/api/aviation/passengers/summary');
  const { data: paxData, loading: paxLoading } = useTrafficData('/api/aviation/passengers');
  const { data: routesData, loading: routesLoading } = useTrafficData('/api/aviation/routes/top');
  const { data: otpData, loading: otpLoading } = useTrafficData('/api/aviation/otp/summary');

  // Build chart data: pivot airport rows into { label, SYDNEY, MELBOURNE, ... }
  const chartData = [];
  if (paxData?.data) {
    const byMonth = {};
    for (const r of paxData.data) {
      const key = `${r.year}-${String(r.month).padStart(2, '0')}`;
      if (!byMonth[key]) byMonth[key] = { label: `${MONTH_NAMES[r.month]} ${r.year}` };
      byMonth[key][r.airport] = r.total_pax;
    }
    chartData.push(...Object.values(byMonth));
  }

  return (
    <>
      {/* ── Summary cards ──────────────────────────────────── */}
      <section className="panel">
        <h3 className="panel-title">Airport passengers — latest month</h3>
        <p className="panel-note">Monthly passenger movements at Australia's five major capital-city airports. Source: BITRE Airport Traffic Data (data.gov.au).</p>
        {summaryLoading ? <div className="chart-loading">Loading…</div> : (
          <div className="avi-summary-cards">
            {summaryData?.data?.map(a => (
              <div key={a.airport} className="avi-card" style={{ borderTopColor: COLOURS[a.airport] }}>
                <div className="avi-card-name">{a.airport}</div>
                <div className="avi-card-period">{MONTH_NAMES[a.month]} {a.year}</div>
                <div className="avi-card-total">{fmtPax(a.total_pax)}</div>
                <div className="avi-card-split">
                  <span>Dom {fmtPax(a.dom_pax)}</span>
                  <span>Int {fmtPax(a.int_pax)}</span>
                </div>
                <div className="avi-card-badges">
                  {a.mom_pct != null && (
                    <span className={`avi-badge ${a.mom_pct >= 0 ? 'up' : 'down'}`}>MoM {fmtPct(a.mom_pct)}</span>
                  )}
                  {a.yoy_pct != null && (
                    <span className={`avi-badge ${a.yoy_pct >= 0 ? 'up' : 'down'}`}>YoY {fmtPct(a.yoy_pct)}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* ── Passenger trend chart ──────────────────────────── */}
      <section className="panel">
        <h3 className="panel-title">Monthly passengers by airport</h3>
        <p className="panel-note">Total passenger movements (arrivals + departures) per month. Domestic and international combined.</p>
        {paxLoading ? <div className="chart-loading">Loading…</div> : (
          <ResponsiveContainer width="100%" height={380}>
            <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
              <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={1} />
              <YAxis tickFormatter={v => fmtPax(v)} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => v?.toLocaleString()} />
              <Legend />
              {AIRPORTS.map(a => (
                <Line key={a} type="monotone" dataKey={a} stroke={COLOURS[a]}
                  strokeWidth={2} dot={false} name={a.charAt(0) + a.slice(1).toLowerCase()} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        )}
      </section>

      {/* ── Top routes table ───────────────────────────────── */}
      <section className="panel">
        <h3 className="panel-title">Top domestic routes — passengers since Jan 2024</h3>
        <p className="panel-note">City-pair route totals across all months. Load factor = percentage of available seats occupied.</p>
        {routesLoading ? <div className="chart-loading">Loading…</div> : (
          <div className="avi-table-wrap">
            <table className="avi-table">
              <thead>
                <tr>
                  <th>#</th><th>Route</th><th>Passengers</th>
                  <th>Flights</th><th>Load factor</th><th>Distance</th>
                </tr>
              </thead>
              <tbody>
                {routesData?.data?.slice(0, 15).map((r, i) => (
                  <tr key={`${r.city1}-${r.city2}`}>
                    <td className="avi-rank">{i + 1}</td>
                    <td>{r.city1.charAt(0) + r.city1.slice(1).toLowerCase()} → {r.city2.charAt(0) + r.city2.slice(1).toLowerCase()}</td>
                    <td className="avi-num">{r.total_passengers?.toLocaleString()}</td>
                    <td className="avi-num">{r.total_flights?.toLocaleString()}</td>
                    <td className="avi-num">{r.avg_load_factor}%</td>
                    <td className="avi-num">{r.distance_km?.toLocaleString()} km</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── OTP leaderboard ────────────────────────────────── */}
      <section className="panel">
        <h3 className="panel-title">On-time performance — route reliability</h3>
        <p className="panel-note">Arrival on-time percentage and cancellation rate by route (all airlines combined). Routes with fewer than 50 scheduled sectors excluded.</p>
        {otpLoading ? <div className="chart-loading">Loading…</div> : (
          <div className="avi-otp-grid">
            <div>
              <h4 className="avi-otp-heading best">Most reliable</h4>
              <table className="avi-table avi-table-compact">
                <thead><tr><th>Route</th><th>On-time</th><th>Cancelled</th></tr></thead>
                <tbody>
                  {otpData?.data?.slice(0, 10).map(r => (
                    <tr key={r.route + '-best'}>
                      <td>{r.route}</td>
                      <td className="avi-num avi-good">{r.ontime_pct}%</td>
                      <td className="avi-num">{r.cancel_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <h4 className="avi-otp-heading worst">Least reliable</h4>
              <table className="avi-table avi-table-compact">
                <thead><tr><th>Route</th><th>On-time</th><th>Cancelled</th></tr></thead>
                <tbody>
                  {otpData?.data?.slice(-10).reverse().map(r => (
                    <tr key={r.route + '-worst'}>
                      <td>{r.route}</td>
                      <td className="avi-num avi-bad">{r.ontime_pct}%</td>
                      <td className="avi-num">{r.cancel_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </section>
    </>
  );
}
