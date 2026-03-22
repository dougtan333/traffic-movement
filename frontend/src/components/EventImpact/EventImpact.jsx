/**
 * EventImpact — cards showing traffic impact of major events.
 * Compares event-window traffic to a day-of-week matched baseline.
 * Metro core stations, Victoria only.
 */
import { useTrafficData } from '../../hooks/useTrafficData';
import './EventImpact.css';

function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function EventImpact() {
  const { data, loading, error } = useTrafficData('/api/traffic/event-impact', {});

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.events?.length) return null;

  // Only show events that have both values
  const events = data.events.filter(e => e.event_avg && e.baseline_avg);

  return (
    <div className="event-impact">
      <div className="event-cards">
        {events.map(ev => {
          const isDown = ev.impact_pct < 0;
          return (
            <div key={ev.date} className={`event-card ${isDown ? 'down' : 'up'}`}>
              <div className="event-card-header">
                <span className="event-name">{ev.event}</span>
                <span className="event-date">{formatDate(ev.date)}</span>
              </div>
              <div className="event-card-body">
                <div className="event-metric">
                  <span className="metric-label">Event window</span>
                  <span className="metric-value">{ev.event_avg.toLocaleString()}</span>
                </div>
                <div className="event-metric">
                  <span className="metric-label">Baseline</span>
                  <span className="metric-value">{ev.baseline_avg.toLocaleString()}</span>
                </div>
                <div className="event-metric impact">
                  <span className="metric-label">Impact</span>
                  <span className={`metric-value ${isDown ? 'negative' : 'positive'}`}>
                    {ev.impact_pct > 0 ? '+' : ''}{ev.impact_pct}%
                  </span>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
