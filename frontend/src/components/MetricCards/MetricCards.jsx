/**
 * MetricCards — summary numbers from the weekly monitor endpoint.
 * Shows baseline, latest week, change vs baseline, and change vs YoY.
 *
 * @param {{ data: object }} props — monitor data for one city
 */
import './MetricCards.css';

export default function MetricCards({ data }) {
  if (!data || !data.latest_week) return null;

  const { baseline_feb26, latest_week, vs_baseline_pct, vs_prior_week_pct, metro_core_stations } = data;

  const stationLabel = metro_core_stations ? `${metro_core_stations} metro core stations` : `${latest_week.stations} stations`;

  const cards = [
    {
      label: `Week of ${parseInt(latest_week.week.slice(8))} ${['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][parseInt(latest_week.week.slice(5,7))-1]}`,
      value: latest_week.avg.toLocaleString(),
      sub: `vehicles/day/station · weekdays · ${stationLabel}`,
    },
    {
      label: 'Feb 2026 baseline',
      value: baseline_feb26 ? baseline_feb26.toLocaleString() : '—',
      sub: `vehicles/day/station · weekdays · ${stationLabel}`,
    },
    {
      label: 'vs baseline',
      value: vs_baseline_pct != null ? `${vs_baseline_pct > 0 ? '+' : ''}${vs_baseline_pct}%` : '—',
      sub: vs_baseline_pct < -3 ? 'below normal' : vs_baseline_pct > 3 ? 'above normal' : 'normal range',
      alert: vs_baseline_pct != null && vs_baseline_pct < -5,
      trend: vs_baseline_pct > 0 ? 'up' : vs_baseline_pct < 0 ? 'down' : null,
    },
    {
      label: 'vs prior week',
      value: vs_prior_week_pct != null ? `${vs_prior_week_pct > 0 ? '+' : ''}${vs_prior_week_pct}%` : '—',
      sub: 'week-on-week',
      trend: vs_prior_week_pct > 0 ? 'up' : vs_prior_week_pct < 0 ? 'down' : null,
    },
  ];

  const trendArrow = (t) => t === 'up' ? '▲ ' : t === 'down' ? '▼ ' : '';
  const cardClass = (card) => {
    if (card.alert) return 'metric-card alert';
    if (card.trend === 'up') return 'metric-card card-up';
    if (card.trend === 'down') return 'metric-card card-down';
    if (card.trend === null && card.value !== '—' && (card.label.includes('vs'))) return 'metric-card card-neutral';
    return 'metric-card';
  };
  const valClass = (card) => {
    if (card.trend === 'up') return 'metric-value val-up';
    if (card.trend === 'down') return 'metric-value val-down';
    return 'metric-value';
  };

  return (
    <div className="metric-cards">
      {cards.map((card, i) => (
        <div key={i} className={cardClass(card)}>
          <div className="metric-label">{card.label}</div>
          <div className={valClass(card)}>{trendArrow(card.trend)}{card.value}</div>
          <div className="metric-sub">{card.sub}</div>
        </div>
      ))}
    </div>
  );
}
