/**
 * SpeedPanel — real-time Melbourne speed overview from Bluetooth sensors.
 * Shows network-wide speed summary + speed distribution bar.
 * Melbourne only — hidden for Sydney.
 *
 * @param {{ city: string }} props
 */
import { useTrafficData } from '../../hooks/useTrafficData';
import {
  ResponsiveContainer, AreaChart, Area, XAxis, YAxis,
  CartesianGrid, Tooltip,
} from 'recharts';
import './SpeedPanel.css';

export default function SpeedPanel({ city }) {
  const { data: snapshot, loading: snapLoading } = useTrafficData('/api/speed/snapshot', {});
  const { data: trend, loading: trendLoading } = useTrafficData('/api/speed/trend', { hours: 4 });

  // Only show for Melbourne
  if (city !== 'melbourne') return null;
  if (snapLoading && trendLoading) return <div className="chart-loading">Loading speed data…</div>;
  if (!snapshot?.summary) return <div className="chart-loading">No speed data yet — poller may not be running</div>;

  const { summary, timestamp } = snapshot;
  const total = summary.slow_links + summary.moderate_links + summary.free_flow_links;
  const slowPct = Math.round((summary.slow_links / total) * 100);
  const modPct = Math.round((summary.moderate_links / total) * 100);
  const freePct = 100 - slowPct - modPct;

  const trendData = (trend?.data || []).map(d => ({
    ...d,
    time: new Date(d.ts).toLocaleTimeString('en-AU', { hour: '2-digit', minute: '2-digit' }),
  }));

  return (
    <div className="speed-panel">
      <div className="speed-metrics">
        <div className="speed-metric">
          <span className="sp-label">Network avg</span>
          <span className="sp-value">{summary.avg_speed_kmh}<small> km/h</small></span>
        </div>
        <div className="speed-metric">
          <span className="sp-label">Links reporting</span>
          <span className="sp-value">{summary.links.toLocaleString()}</span>
        </div>
        <div className="speed-metric">
          <span className="sp-label">Avg delay</span>
          <span className="sp-value">{summary.avg_delay_sec}<small>s</small></span>
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
          <div className="dist-segment dist-free" style={{ width: `${freePct}%` }}>{freePct}%</div>
          <div className="dist-segment dist-mod" style={{ width: `${modPct}%` }}>{modPct}%</div>
          <div className="dist-segment dist-slow" style={{ width: `${slowPct}%` }}>{slowPct}%</div>
        </div>
        <div className="dist-legend">
          <span><i className="dot dot-free" /> Free-flow (40+ km/h)</span>
          <span><i className="dot dot-mod" /> Moderate (20–40)</span>
          <span><i className="dot dot-slow" /> Slow (&lt;20)</span>
        </div>
      </div>

      {trendData.length > 1 && (
        <div className="chart-container">
          <ResponsiveContainer width="100%" height={180}>
            <AreaChart data={trendData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#eee" vertical={false} />
              <XAxis dataKey="time" tick={{ fontSize: 11 }} />
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
