/**
 * SpeedPanel — real-time Melbourne speed overview from Bluetooth sensors.
 * Supports filtering by road name or freeways only.
 */
import { useState, useEffect } from 'react';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip,
} from 'recharts';
import { API_URL } from '../../constants';
import './SpeedPanel.css';

export default function SpeedPanel() {
  const [filter, setFilter] = useState('all');
  const [trendHours, setTrendHours] = useState(24);
  const [roads, setRoads] = useState([]);
  const [snapshot, setSnapshot] = useState(null);
  const [trend, setTrend] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch road list once
  useEffect(() => {
    fetch(`${API_URL}/api/speed/roads`)
      .then(r => r.json())
      .then(d => setRoads(d.roads || []))
      .catch(() => {});
  }, []);

  // Fetch snapshot + trend when filter or time range changes
  useEffect(() => {
    const params = filter === 'freeways' ? 'freeways=true'
      : filter !== 'all' ? `road=${encodeURIComponent(filter)}`
      : '';
    Promise.all([
      fetch(`${API_URL}/api/speed/snapshot?${params}`).then(r => r.json()),
      fetch(`${API_URL}/api/speed/trend?hours=${trendHours}&${params}`).then(r => r.json()),
    ]).then(([snap, tr]) => {
      setSnapshot(snap);
      setTrend(tr);
      setLoading(false);
    }).catch(() => setLoading(false));
  }, [filter, trendHours]);

  if (loading && !snapshot) return <div className="chart-loading">Loading speed data…</div>;
  if (!snapshot?.summary) return <div className="chart-loading">No speed data yet — poller may not be running</div>;

  const { summary, timestamp, thresholds } = snapshot;
  const freeMin = thresholds?.free_flow_min_kmh ?? 40;
  const slowMax = thresholds?.slow_max_kmh ?? 20;
  const refSpeed = thresholds?.ref_speed_kmh ?? 80;

  // Use trend distribution for the selected period, fallback to snapshot (latest interval)
  const dist = trend?.distribution || summary;
  const total = (dist.slow_links || 0) + (dist.moderate_links || 0) + (dist.free_flow_links || 0);
  const slowPct = total ? Math.round((dist.slow_links / total) * 100) : 0;
  const modPct = total ? Math.round((dist.moderate_links / total) * 100) : 0;
  const freePct = total ? 100 - slowPct - modPct : 0;

  const trendData = (trend?.data || []).map(d => {
    const dt = new Date(d.ts);
    let time;
    if (trendHours <= 24) {
      time = dt.toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' });
    } else {
      // Round to nearest hour, show day above time
      const rounded = new Date(dt);
      rounded.setMinutes(dt.getMinutes() >= 30 ? 60 : 0, 0, 0);
      const day = rounded.toLocaleDateString('en-AU', { weekday: 'short', day: 'numeric' });
      const hr = rounded.toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' });
      time = `${day}\n${hr}`;
    }
    return { ...d, time };
  });

  // Custom X-axis tick for multi-line labels (day + time) on 3d/7d views
  const MultiLineTick = ({ x, y, payload }) => {
    const parts = (payload.value || '').split('\n');
    if (parts.length === 1) {
      return <text x={x} y={y + 10} textAnchor="middle" fontSize={10} fill="#666">{parts[0]}</text>;
    }
    return (
      <g>
        <text x={x} y={y + 8} textAnchor="middle" fontSize={9} fill="#999">{parts[0]}</text>
        <text x={x} y={y + 20} textAnchor="middle" fontSize={10} fill="#666">{parts[1]}</text>
      </g>
    );
  };

  // Group roads for dropdown: freeways first, then arterials
  const fwys = roads.filter(r => r.is_freeway);
  const arts = roads.filter(r => !r.is_freeway).slice(0, 30);

  return (
    <div className="speed-panel">
      <h3 className="panel-title">Live speed — Bluetooth sensors</h3>
      <p className="panel-note">4,711 links across freeways and arterials · speed from Bluetooth travel time between receiver pairs</p>
      <div className="speed-filter-row">
        <select
          className="speed-filter"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">All links ({summary.links})</option>
          <option value="freeways">Freeways only</option>
          <optgroup label="Freeways">
            {fwys.map(r => (
              <option key={r.name} value={r.name}>{r.name} ({r.links})</option>
            ))}
          </optgroup>
          <optgroup label="Major arterials">
            {arts.map(r => (
              <option key={r.name} value={r.name}>{r.name} ({r.links})</option>
            ))}
          </optgroup>
        </select>
        <div className="speed-range-btns">
          {[
            { label: '24h', h: 24 },
            { label: '3d', h: 72 },
            { label: '7d', h: 168 },
            { label: '14d', h: 336 },
          ].map(b => (
            <button key={b.h}
              className={`speed-range-btn ${trendHours === b.h ? 'active' : ''}`}
              onClick={() => setTrendHours(b.h)}
            >{b.label}</button>
          ))}
        </div>
      </div>

      <div className="speed-metrics">
        <div className="speed-metric">
          <span className="sp-label">Avg speed</span>
          <span className="sp-value">{summary.avg_speed_kmh}<small> km/h</small></span>
        </div>
        <div className="speed-metric">
          <span className="sp-label">Links</span>
          <span className="sp-value">{summary.links.toLocaleString()}</span>
        </div>
        <div className="speed-metric">
          <span className="sp-label">Avg delay</span>
          <span className="sp-value">{Math.max(0, summary.avg_delay_sec)}<small>s</small></span>
        </div>
        <div className="speed-metric">
          <span className="sp-label">Updated</span>
          <span className="sp-value sp-time">
            {new Date(timestamp).toLocaleDateString('en-AU', { day: 'numeric', month: 'short' })}{' '}
            {new Date(timestamp).toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' })}
          </span>
        </div>
      </div>

      <div className="speed-distribution">
        <div className="dist-bar">
          {freePct > 0 && <div className="dist-segment dist-free" style={{ width: `${freePct}%` }}>{freePct > 5 ? `${freePct}%` : ''}</div>}
          {modPct > 0 && <div className="dist-segment dist-mod" style={{ width: `${modPct}%` }}>{modPct > 5 ? `${modPct}%` : ''}</div>}
          {slowPct > 0 && <div className="dist-segment dist-slow" style={{ width: `${slowPct}%` }}>{slowPct > 5 ? `${slowPct}%` : ''}</div>}
        </div>
        <div className="dist-legend">
          <span><i className="dot dot-free" /> Free-flow ({freeMin}+ km/h)</span>
          <span><i className="dot dot-mod" /> Moderate ({slowMax}–{freeMin})</span>
          <span><i className="dot dot-slow" /> Slow (&lt;{slowMax})</span>
        </div>
      </div>

      {trendData.length > 1 && (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={trendHours <= 24 ? 180 : trendHours <= 168 ? 280 : 300}>
            <AreaChart data={trendData} margin={{ top: 5, right: 20, bottom: trendHours > 24 ? 20 : 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
              <XAxis
                dataKey="time"
                tick={trendHours > 24 ? <MultiLineTick /> : { fontSize: 10 }}
                interval={trendHours <= 24 ? 'preserveStartEnd' : Math.floor(trendData.length / 8)}
                height={trendHours > 24 ? 40 : 20}
              />
              <YAxis domain={[0, 'auto']} tick={{ fontSize: 11 }} label={{ value: 'km/h', angle: -90, position: 'insideLeft', fontSize: 11 }} />
              <Tooltip formatter={(v) => [`${v} km/h`, 'Avg speed']} />
              <Area type="monotone" dataKey="avg_speed" stroke="#2A9D8F" fill="#2A9D8F" fillOpacity={0.15} strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
