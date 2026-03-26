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
import { useState, useMemo } from 'react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip,
  Legend, ResponsiveContainer, BarChart, Bar, Cell,
  AreaChart, Area,
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

/**
 * InternationalTravel — stacked area chart (dom/int split) + international YoY table.
 * Shows how international travel compares to domestic across all 5 airports.
 */
function InternationalTravel({ data, loading }) {
  const [selectedAirport, setSelectedAirport] = useState('MELBOURNE');

  const { stackedData, yoyTableData } = useMemo(() => {
    if (!data?.data?.length) return { stackedData: [], yoyTableData: [] };

    // Stacked area: filter to selected airport, one point per month
    const airportRows = data.data.filter(r => r.airport === selectedAirport);
    const sd = airportRows.map(r => ({
      label: `${MONTH_NAMES[r.month]} ${String(r.year).slice(2)}`,
      key: `${r.year}-${String(r.month).padStart(2, '0')}`,
      domestic: r.dom_pax,
      international: r.int_pax,
      int_pct: r.int_pct,
    }));

    // YoY table: all airports, 2025 international pax per month + YoY %
    const airports = ['SYDNEY', 'MELBOURNE', 'BRISBANE', 'PERTH', 'ADELAIDE'];
    const months = [1,2,3,4,5,6,7,8,9,10,11,12];
    const idx = {};
    for (const r of data.data) idx[`${r.airport}|${r.year}|${r.month}`] = r;

    const ytd = airports.map(ap => {
      const monthCells = months.map(m => {
        const d25 = idx[`${ap}|2025|${m}`];
        const d24 = idx[`${ap}|2024|${m}`];
        return {
          month: m,
          int25: d25?.int_pax ?? null,
          int24: d24?.int_pax ?? null,
          yoy: d25?.int_yoy_pct ?? null,
        };
      });
      return { airport: ap, monthCells };
    });

    return { stackedData: sd, yoyTableData: ytd };
  }, [data, selectedAirport]);

  if (loading) return <section className="panel-secondary"><div className="chart-loading">Loading…</div></section>;
  if (!data?.data?.length) return null;

  return (
    <>
      {/* Stacked area: dom/int split */}
      <section className="panel-secondary">
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 4 }}>
          <h3 className="panel-title" style={{ margin: 0 }}>Domestic vs international passengers</h3>
          <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
            {AIRPORTS.map(ap => (
              <button key={ap} className={`avi-toggle ${selectedAirport === ap ? 'active' : ''}`}
                onClick={() => setSelectedAirport(ap)}>
                {ap.charAt(0) + ap.slice(1).toLowerCase()}
              </button>
            ))}
          </div>
        </div>
        <p className="panel-note">Monthly passenger split · {selectedAirport.charAt(0) + selectedAirport.slice(1).toLowerCase()} airport</p>

        <ResponsiveContainer width="100%" height={320}>
          <AreaChart data={stackedData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
            <XAxis dataKey="label" tick={{ fontSize: 10 }} interval={2} />
            <YAxis tickFormatter={v => fmtPax(v)} tick={{ fontSize: 11 }} />
            <Tooltip formatter={(v) => v?.toLocaleString()} />
            <Legend />
            <Area type="monotone" dataKey="domestic" stackId="1"
              stroke="#1B3A5C" fill="#1B3A5C" fillOpacity={0.6} name="Domestic" />
            <Area type="monotone" dataKey="international" stackId="1"
              stroke="#2A9D8F" fill="#2A9D8F" fillOpacity={0.6} name="International" />
          </AreaChart>
        </ResponsiveContainer>
      </section>

      {/* International YoY table */}
      <section className="panel-secondary">
        <h3 className="panel-title">International passengers — year-on-year (2025 vs 2024)</h3>
        <p className="panel-note">Monthly international pax per airport · YoY % change</p>
        <div className="avi-table-wrap">
          <table className="avi-table avi-yoy-table">
            <thead>
              <tr>
                <th className="avi-yoy-route">Airport</th>
                {[1,2,3,4,5,6,7,8,9,10,11,12].map(m => (
                  <th key={m} className="avi-yoy-month">{MONTH_NAMES[m]}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {yoyTableData.map(row => (
                <tr key={row.airport} className="avi-yoy-row">
                  <td className="avi-yoy-route-cell" style={{ borderLeftColor: COLOURS[row.airport], borderLeftWidth: 3, borderLeftStyle: 'solid' }}>
                    {row.airport.charAt(0) + row.airport.slice(1).toLowerCase()}
                  </td>
                  {row.monthCells.map(c => (
                    <td key={c.month} className="avi-yoy-cell">
                      {c.int25 != null ? (
                        <>
                          <span className="avi-yoy-pax">{fmtPax(c.int25)}</span>
                          {c.yoy != null && (
                            <span className={`avi-yoy-delta ${c.yoy >= 0 ? 'up' : 'down'}`}>
                              {c.yoy >= 0 ? '+' : ''}{c.yoy.toFixed(1)}%
                            </span>
                          )}
                        </>
                      ) : <span className="avi-yoy-na">—</span>}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

/**
 * MelbourneOtpYoY — line chart + table showing monthly on-time performance
 * per Melbourne route, with 2024 vs 2025 side by side and YoY delta.
 */
function MelbourneOtpYoY({ data, loading }) {
  const [selectedRoute, setSelectedRoute] = useState(null);
  const [metric, setMetric] = useState('ontime'); // 'ontime' or 'cancel'

  const { routes, chartData, tableRows } = useMemo(() => {
    if (!data?.data?.length) return { routes: [], chartData: [], tableRows: [] };

    const seen = new Set();
    const routeList = [];
    for (const r of data.data) {
      if (!seen.has(r.route)) { seen.add(r.route); routeList.push(r.route); }
    }

    // Index by route|year|month
    const idx = {};
    for (const r of data.data) idx[`${r.route}|${r.year}|${r.month}`] = r;

    // Chart data: month 1-12, series per route for 2024 + 2025
    const months = [1,2,3,4,5,6,7,8,9,10,11,12];
    const cd = months.map(m => {
      const point = { month: m, monthLabel: MONTH_NAMES[m] };
      for (const rt of routeList) {
        const d24 = idx[`${rt}|2024|${m}`];
        const d25 = idx[`${rt}|2025|${m}`];
        if (d24) point[`${rt} 2024`] = metric === 'ontime' ? d24.ontime_pct : d24.cancel_pct;
        if (d25) point[`${rt} 2025`] = metric === 'ontime' ? d25.ontime_pct : d25.cancel_pct;
      }
      return point;
    });

    // Table rows
    const tr = routeList.map(rt => {
      // Extract the non-Melbourne city + direction arrow for display
      const sample = data.data.find(r => r.route === rt);
      const other = sample.from === 'Melbourne' ? sample.to : sample.from;
      const direction = sample.from === 'Melbourne' ? '→' : '←';
      const label = `${direction} ${other}`;
      const monthCells = months.map(m => {
        const d24 = idx[`${rt}|2024|${m}`];
        const d25 = idx[`${rt}|2025|${m}`];
        const val25 = d25 ? (metric === 'ontime' ? d25.ontime_pct : d25.cancel_pct) : null;
        const val24 = d24 ? (metric === 'ontime' ? d24.ontime_pct : d24.cancel_pct) : null;
        const delta = (val25 != null && val24 != null) ? (val25 - val24) : null;
        return { month: m, val25, val24, delta };
      });
      return { route: rt, label, other, monthCells };
    });

    return { routes: routeList, chartData: cd, tableRows: tr };
  }, [data, metric]);

  if (loading) return <section className="panel-secondary"><div className="chart-loading">Loading…</div></section>;
  if (!routes.length) return null;

  const chartRoutes = selectedRoute
    ? routes.filter(r => r === selectedRoute)
    : routes.slice(0, 3);

  const isOntime = metric === 'ontime';

  return (
    <section className="panel-secondary">
      <h3 className="panel-title">Melbourne on-time performance — year-on-year</h3>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8 }}>
        <p className="panel-note" style={{ margin: 0 }}>
          Monthly {isOntime ? 'arrival on-time %' : 'cancellation %'} per route · solid = 2025, dashed = 2024 · click a row to isolate
        </p>
        <div style={{ display: 'flex', gap: 4, marginLeft: 'auto' }}>
          <button className={`avi-toggle ${isOntime ? 'active' : ''}`} onClick={() => setMetric('ontime')}>On-time %</button>
          <button className={`avi-toggle ${!isOntime ? 'active' : ''}`} onClick={() => setMetric('cancel')}>Cancellation %</button>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={340}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis dataKey="monthLabel" tick={{ fontSize: 12 }} />
          <YAxis domain={isOntime ? [50, 100] : [0, 'auto']} tickFormatter={v => `${v}%`} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v) => v != null ? `${v}%` : '—'} />
          <Legend />
          {chartRoutes.map((rt, i) => {
            const colour = ROUTE_COLOURS[routes.indexOf(rt) % ROUTE_COLOURS.length];
            const sample = data.data.find(r => r.route === rt);
            const other = sample ? (sample.from === 'Melbourne' ? sample.to : sample.from) : rt;
            const dir = sample?.from === 'Melbourne' ? '→' : '←';
            const label = `${dir} ${other}`;
            return [
              <Line key={`${rt}-25`} type="monotone" dataKey={`${rt} 2025`}
                stroke={colour} strokeWidth={2.5} dot={{ r: 3 }}
                name={`${label} 2025`} connectNulls />,
              <Line key={`${rt}-24`} type="monotone" dataKey={`${rt} 2024`}
                stroke={colour} strokeWidth={1.5} strokeDasharray="6 3" dot={false}
                name={`${label} 2024`} connectNulls />,
            ];
          })}
        </LineChart>
      </ResponsiveContainer>

      <div className="avi-table-wrap" style={{ marginTop: 16 }}>
        <table className="avi-table avi-yoy-table">
          <thead>
            <tr>
              <th className="avi-yoy-route">Route</th>
              {[1,2,3,4,5,6,7,8,9,10,11,12].map(m => (
                <th key={m} className="avi-yoy-month">{MONTH_NAMES[m]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tableRows.map(row => (
              <tr key={row.route}
                className={`avi-yoy-row ${selectedRoute === row.route ? 'avi-yoy-selected' : ''}`}
                onClick={() => setSelectedRoute(selectedRoute === row.route ? null : row.route)}>
                <td className="avi-yoy-route-cell">{row.label}</td>
                {row.monthCells.map(c => (
                  <td key={c.month} className="avi-yoy-cell">
                    {c.val25 != null ? (
                      <>
                        <span className="avi-yoy-pax">{c.val25}%</span>
                        {c.delta != null && (
                          <span className={`avi-yoy-delta ${
                            isOntime ? (c.delta >= 0 ? 'up' : 'down') : (c.delta <= 0 ? 'up' : 'down')
                          }`}>
                            {c.delta >= 0 ? '+' : ''}{c.delta.toFixed(1)}pp
                          </span>
                        )}
                      </>
                    ) : <span className="avi-yoy-na">—</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

/** Route colours for chart lines */
const ROUTE_COLOURS = ['#2A9D8F', '#E9C46A', '#F4A261', '#6D2E46', '#264653', '#e76f51', '#606c38', '#bc6c25', '#8338ec', '#06d6a0'];

/**
 * MelbourneRoutesYoY — line chart + table showing monthly passengers per
 * Melbourne route, with 2024 vs 2025 side by side and YoY % change.
 */
function MelbourneRoutesYoY({ data, loading }) {
  const [selectedRoute, setSelectedRoute] = useState(null);

  // Derive route list, chart data, and table data from raw API response
  const { routes, chartData, tableRows } = useMemo(() => {
    if (!data?.data?.length) return { routes: [], chartData: [], tableRows: [] };

    // Get unique routes, preserve server order (by total pax desc)
    const seen = new Set();
    const routeList = [];
    for (const r of data.data) {
      const key = `${r.city1}-${r.city2}`;
      if (!seen.has(key)) { seen.add(key); routeList.push({ key, city1: r.city1, city2: r.city2 }); }
    }

    // Build chart: one point per month, two series per route (2024 solid, 2025 dashed)
    // X-axis = month number (1-12), so both years overlay on the same axis
    const byRouteYearMonth = {};
    for (const r of data.data) {
      const rk = `${r.city1}-${r.city2}`;
      const k = `${rk}|${r.year}|${r.month}`;
      byRouteYearMonth[k] = r;
    }

    // Chart data: array of { month, monthLabel, "MEL-SYD 2024": pax, "MEL-SYD 2025": pax, ... }
    const months = [1,2,3,4,5,6,7,8,9,10,11,12];
    const cd = months.map(m => {
      const point = { month: m, monthLabel: MONTH_NAMES[m] };
      for (const rt of routeList) {
        const d24 = byRouteYearMonth[`${rt.key}|2024|${m}`];
        const d25 = byRouteYearMonth[`${rt.key}|2025|${m}`];
        if (d24) point[`${rt.key} 2024`] = d24.passengers;
        if (d25) point[`${rt.key} 2025`] = d25.passengers;
      }
      return point;
    });

    // Table: one row per route, columns = months, cells show 2025 pax + YoY %
    const tr = routeList.map(rt => {
      const label = `${rt.city1.charAt(0) + rt.city1.slice(1).toLowerCase()} → ${rt.city2.charAt(0) + rt.city2.slice(1).toLowerCase()}`;
      const monthCells = months.map(m => {
        const d24 = byRouteYearMonth[`${rt.key}|2024|${m}`];
        const d25 = byRouteYearMonth[`${rt.key}|2025|${m}`];
        const pax25 = d25?.passengers;
        const pax24 = d24?.passengers;
        const yoy = (pax25 != null && pax24) ? ((pax25 - pax24) / pax24 * 100) : null;
        return { month: m, pax25, pax24, yoy };
      });
      return { key: rt.key, label, monthCells };
    });

    return { routes: routeList, chartData: cd, tableRows: tr };
  }, [data]);

  if (loading) return <section className="panel-secondary"><div className="chart-loading">Loading…</div></section>;
  if (!routes.length) return null;

  // If a route is selected, only chart that route; otherwise show top 3
  const chartRoutes = selectedRoute
    ? routes.filter(r => r.key === selectedRoute)
    : routes.slice(0, 3);

  return (
    <section className="panel-secondary">
      <h3 className="panel-title">Melbourne domestic routes — year-on-year</h3>
      <p className="panel-note">Monthly passengers per route · solid = 2025, dashed = 2024 · click a route row to isolate</p>

      {/* Chart */}
      <ResponsiveContainer width="100%" height={340}>
        <LineChart data={chartData} margin={{ top: 5, right: 20, left: 10, bottom: 5 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e0e0e0" />
          <XAxis dataKey="monthLabel" tick={{ fontSize: 12 }} />
          <YAxis tickFormatter={v => fmtPax(v)} tick={{ fontSize: 11 }} />
          <Tooltip formatter={(v) => v?.toLocaleString()} />
          <Legend />
          {chartRoutes.map((rt, i) => {
            const colour = ROUTE_COLOURS[routes.indexOf(rt) % ROUTE_COLOURS.length];
            const other = rt.city1 === 'MELBOURNE' ? rt.city2 : rt.city1;
            const shortLabel = other.charAt(0) + other.slice(1).toLowerCase();
            return [
              <Line key={`${rt.key}-25`} type="monotone" dataKey={`${rt.key} 2025`}
                stroke={colour} strokeWidth={2.5} dot={{ r: 3 }}
                name={`${shortLabel} 2025`} connectNulls />,
              <Line key={`${rt.key}-24`} type="monotone" dataKey={`${rt.key} 2024`}
                stroke={colour} strokeWidth={1.5} strokeDasharray="6 3" dot={false}
                name={`${shortLabel} 2024`} connectNulls />,
            ];
          })}
        </LineChart>
      </ResponsiveContainer>

      {/* Table */}
      <div className="avi-table-wrap" style={{ marginTop: 16 }}>
        <table className="avi-table avi-yoy-table">
          <thead>
            <tr>
              <th className="avi-yoy-route">Route</th>
              {[1,2,3,4,5,6,7,8,9,10,11,12].map(m => (
                <th key={m} className="avi-yoy-month">{MONTH_NAMES[m]}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {tableRows.map((row) => (
              <tr key={row.key}
                className={`avi-yoy-row ${selectedRoute === row.key ? 'avi-yoy-selected' : ''}`}
                onClick={() => setSelectedRoute(selectedRoute === row.key ? null : row.key)}>
                <td className="avi-yoy-route-cell">{row.label}</td>
                {row.monthCells.map(c => (
                  <td key={c.month} className="avi-yoy-cell">
                    {c.pax25 != null ? (
                      <>
                        <span className="avi-yoy-pax">{fmtPax(c.pax25)}</span>
                        {c.yoy != null && (
                          <span className={`avi-yoy-delta ${c.yoy >= 0 ? 'up' : 'down'}`}>
                            {c.yoy >= 0 ? '+' : ''}{c.yoy.toFixed(1)}%
                          </span>
                        )}
                      </>
                    ) : <span className="avi-yoy-na">—</span>}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

export default function AviationPanel() {
  const { data: summaryData, loading: summaryLoading } = useTrafficData('/api/aviation/passengers/summary');
  const { data: paxData, loading: paxLoading } = useTrafficData('/api/aviation/passengers');
  const { data: routesData, loading: routesLoading } = useTrafficData('/api/aviation/routes/top');
  const { data: otpData, loading: otpLoading } = useTrafficData('/api/aviation/otp/summary');
  const { data: routesYoyData, loading: routesYoyLoading } = useTrafficData('/api/aviation/routes/yoy');
  const { data: otpYoyData, loading: otpYoyLoading } = useTrafficData('/api/aviation/otp/yoy');
  const { data: intlData, loading: intlLoading } = useTrafficData('/api/aviation/international');

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
      <section className="panel-hero">
        <h3 className="panel-title">
          Airport passengers
          {summaryData?.data?.[0] && ` — ${MONTH_NAMES[summaryData.data[0].month]} ${summaryData.data[0].year}`}
        </h3>
        <p className="panel-note">Five capital-city airports · BITRE monthly traffic data (data.gov.au)</p>
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
      <section className="panel-secondary">
        <h3 className="panel-title">Monthly passengers by airport</h3>
        <p className="panel-note">Arrivals + departures per month · domestic and international combined</p>
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

      {/* ── International travel ───────────────────────────── */}
      <InternationalTravel data={intlData} loading={intlLoading} />

      {/* ── Top routes table ───────────────────────────────── */}
      <section className="panel-secondary">
        <h3 className="panel-title">Top domestic routes — passengers since Jan 2024</h3>
        <p className="panel-note">City-pair totals · load factor = % of available seats occupied</p>
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

      {/* ── Melbourne routes YoY ───────────────────────────── */}
      <MelbourneRoutesYoY data={routesYoyData} loading={routesYoyLoading} />

      {/* ── OTP leaderboard ────────────────────────────────── */}
      <section className="panel-secondary">
        <h3 className="panel-title">On-time performance — route reliability</h3>
        <p className="panel-note">Arrival on-time % and cancellation rate by route · min 50 scheduled sectors</p>
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

      {/* ── Melbourne OTP YoY ──────────────────────────────── */}
      <MelbourneOtpYoY data={otpYoyData} loading={otpYoyLoading} />
    </>
  );
}
