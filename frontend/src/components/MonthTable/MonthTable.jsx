/**
 * MonthTable — tabular month-on-month comparison with YoY % change.
 * Shows the last 12 months with directional indicators.
 *
 * Victoria only.
 */
import { useTrafficData } from '../../hooks/useTrafficData';
import './MonthTable.css';

export default function MonthTable() {
  const { data, loading, error } = useTrafficData('/api/traffic/month-on-month');

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.data?.length) return null;

  // Show last 12 months
  const rows = data.data.slice(-12);

  const formatMonth = (m) => {
    const d = new Date(m);
    return d.toLocaleDateString('en-AU', { month: 'short', year: 'numeric' });
  };

  const arrow = (v) => {
    if (v == null) return '';
    if (v > 2) return '▲';
    if (v < -2) return '▼';
    return '→';
  };

  const yoyClass = (v) => {
    if (v == null) return '';
    if (v > 2) return 'up';
    if (v < -2) return 'down';
    return 'flat';
  };

  return (
    <div className="chart-container table-scroll">
      <table className="month-table">
        <thead>
          <tr>
            <th>Month</th>
            <th className="num">Vehicles/day/station</th>
            <th className="num">Stations</th>
            <th className="num">Prior year</th>
            <th className="num">YoY change</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(r => (
            <tr key={r.month}>
              <td>{formatMonth(r.month)}</td>
              <td className="num">{r.avg.toLocaleString()}</td>
              <td className="num">{r.stations}</td>
              <td className="num">{r.yoy_avg ? r.yoy_avg.toLocaleString() : '—'}</td>
              <td className={`num yoy ${yoyClass(r.yoy_pct)}`}>
                {r.yoy_pct != null ? `${arrow(r.yoy_pct)} ${r.yoy_pct > 0 ? '+' : ''}${r.yoy_pct}%` : '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
