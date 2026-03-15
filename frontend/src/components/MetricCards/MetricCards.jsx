/**
 * MetricCards — summary numbers from the weekly monitor endpoint.
 * Shows baseline, latest week, change vs baseline, and change vs YoY.
 *
 * @param {{ data: object }} props — monitor data for one city
 */
import './MetricCards.css';

export default function MetricCards({ data }) {
  if (!data || !data.latest_week) return null;

  const { baseline_feb26, latest_week, vs_baseline_pct, vs_prior_week_pct } = data;

  const cards = [
    {
      label: `Week of ${latest_week.week.slice(5)}`,
      value: latest_week.avg.toLocaleString(),
      sub: `${latest_week.weekdays || latest_week.days} weekdays`,
    },
    {
      label: 'Feb 2026 baseline',
      value: baseline_feb26 ? baseline_feb26.toLocaleString() : '—',
      sub: 'weekday avg/station',
    },
    {
      label: 'vs baseline',
      value: vs_baseline_pct != null ? `${vs_baseline_pct > 0 ? '+' : ''}${vs_baseline_pct}%` : '—',
      sub: vs_baseline_pct < -3 ? '▼ below normal' : vs_baseline_pct > 3 ? '▲ above normal' : '→ normal range',
      alert: vs_baseline_pct != null && vs_baseline_pct < -5,
    },
    {
      label: 'vs prior week',
      value: vs_prior_week_pct != null ? `${vs_prior_week_pct > 0 ? '+' : ''}${vs_prior_week_pct}%` : '—',
      sub: 'week-on-week',
    },
  ];

  return (
    <div className="metric-cards">
      {cards.map((card, i) => (
        <div key={i} className={`metric-card ${card.alert ? 'alert' : ''}`}>
          <div className="metric-label">{card.label}</div>
          <div className="metric-value">{card.value}</div>
          <div className="metric-sub">{card.sub}</div>
        </div>
      ))}
    </div>
  );
}
