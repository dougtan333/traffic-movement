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
  const total = summary.slow_links + summary.moderate_links + summary.free_flow_links;
  const slowPct = total ? Math.round((summary.slow_links / total) * 100) : 0;
  const modPct = total ? Math.round((summary.moderate_links / total) * 100) : 0;
  const freePct = total ? 100 - slowPct - modPct : 0;

  const trendData = (trend?.data || []).map(d => ({
    ...d,
    time: trendHours <= 24
      ? new Date(d.ts).toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' })
      : new Date(d.ts).toLocaleDateString('en-AU', { weekday: 'short', hour: '2-digit', minute: '2-digit' }),
  }));

  // Group roads for dropdown: freeways first, then arterials
  const fwys = roads.filter(r => r.is_freeway);
  const arts = roads.filter(r => !r.is_freeway).slice(0, 30);

  return (
    <div className="speed-panel">
      <h3 className="panel-title">Live speed — Bluetooth sensors</h3>
      <p className="panel-note">A link is the stretch of road between two Bluetooth receivers, typically on freeways and major arterials. Speed is measured from the travel time of detected Bluetooth devices passing between the pair.</p>
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
            { label: '12h', h: 12 },
            { label: '24h', h: 24 },
            { label: '3d', h: 72 },
            { label: '7d', h: 168 },
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
          <ResponsiveContainer width="100%" height={trendHours > 24 ? 260 : 180}>
            <AreaChart data={trendData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 10 }} interval={trendHours <= 24 ? 'preserveStartEnd' : Math.floor(trendData.length / 12)} />
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
