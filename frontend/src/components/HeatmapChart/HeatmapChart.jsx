/**
 * HeatmapChart — hour × day-of-week grid showing traffic intensity.
 * Green = light traffic, amber = moderate, red = heavy.
 * Built as a pure HTML/CSS grid (Recharts doesn't do heatmaps well).
 *
 * @param {{ }} props
 */
import { useTrafficData } from '../../hooks/useTrafficData';
import { CITY_COLORS } from '../../constants';
import './HeatmapChart.css';

const HOUR_LABELS = Array.from({ length: 24 }, (_, i) => {
  const h = i % 12 || 12;
  return `${h}${i < 12 ? 'a' : 'p'}`;
});

const DAY_ORDER = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

function getColor(value, max) {
  const ratio = value / max;
  if (ratio < 0.2) return 'var(--hm-1)';
  if (ratio < 0.35) return 'var(--hm-2)';
  if (ratio < 0.5) return 'var(--hm-3)';
  if (ratio < 0.65) return 'var(--hm-4)';
  if (ratio < 0.8) return 'var(--hm-5)';
  return 'var(--hm-6)';
}

export default function HeatmapChart() {
  const { data, loading, error } = useTrafficData('/api/traffic/heatmap', {
    weeks: 12,
  });

  if (loading) return <div className="chart-loading">Loading heatmap…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  const max = Math.max(...data.data.map(d => d.avg_count));

  // Build grid: rows = days, columns = hours
  const grid = {};
  data.data.forEach(d => {
    if (!grid[d.day]) grid[d.day] = {};
    grid[d.day][d.hour] = d.avg_count;
  });

  return (
    <div className="chart-container">
      <div className="heatmap-legend">
        <span className="heatmap-legend-label">Light</span>
        <span className="heatmap-swatch" style={{ background: 'var(--hm-1)' }} />
        <span className="heatmap-swatch" style={{ background: 'var(--hm-2)' }} />
        <span className="heatmap-swatch" style={{ background: 'var(--hm-3)' }} />
        <span className="heatmap-swatch" style={{ background: 'var(--hm-4)' }} />
        <span className="heatmap-swatch" style={{ background: 'var(--hm-5)' }} />
        <span className="heatmap-swatch" style={{ background: 'var(--hm-6)' }} />
        <span className="heatmap-legend-label">Heavy</span>
      </div>
      <div className="heatmap-grid">
        <div className="heatmap-row heatmap-header">
          <div className="heatmap-label" />
          {HOUR_LABELS.map((h, i) => (
            <div key={i} className="heatmap-hour-label">{i % 2 === 0 ? h : ''}</div>
          ))}
        </div>
        {DAY_ORDER.map(day => (
          <div key={day} className="heatmap-row">
            <div className="heatmap-label">{day}</div>
            {Array.from({ length: 24 }, (_, h) => {
              const val = grid[day]?.[h] || 0;
              return (
                <div
                  key={h}
                  className="heatmap-cell"
                  style={{ background: getColor(val, max) }}
                  title={`${day} ${HOUR_LABELS[h]}: ${val.toLocaleString()} avg/station`}
                />
              );
            })}
          </div>
        ))}
      </div>
    </div>
  );
}
