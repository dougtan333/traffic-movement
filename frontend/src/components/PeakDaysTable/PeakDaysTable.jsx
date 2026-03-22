/**
 * PeakDaysTable — ranks the busiest and quietest weekdays.
 * Two side-by-side tables with calendar context annotations.
 * Metro core stations, Victoria only.
 */
import { useTrafficData } from '../../hooks/useTrafficData';
import './PeakDaysTable.css';

function formatDate(dateStr) {
  const d = new Date(dateStr);
  return d.toLocaleDateString('en-AU', { day: 'numeric', month: 'short', year: 'numeric' });
}

export default function PeakDaysTable() {
  const { data, loading, error } = useTrafficData('/api/traffic/peak-days', { top_n: 15 });

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.busiest?.length) return null;

  const maxVal = data.busiest[0]?.avg_per_station || 1;

  return (
    <div className="peak-days">
      <div className="peak-days-grid">
        <div className="peak-col">
          <h4 className="peak-col-title busiest">Busiest weekdays</h4>
          <table className="peak-table">
            <thead><tr><th>#</th><th>Date</th><th>Day</th><th>Vehicles/day/station</th><th>Context</th></tr></thead>
            <tbody>
              {data.busiest.map((d, i) => (
                <tr key={d.date}>
                  <td className="rank">{i + 1}</td>
                  <td>{formatDate(d.date)}</td>
                  <td>{d.dow}</td>
                  <td>
                    <div className="bar-cell">
                      <div className="bar busiest-bar" style={{ width: `${(d.avg_per_station / maxVal) * 100}%` }} />
                      <span>{d.avg_per_station.toLocaleString()}</span>
                    </div>
                  </td>
                  <td className="context">{d.context || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="peak-col">
          <h4 className="peak-col-title quietest">Quietest weekdays</h4>
          <table className="peak-table">
            <thead><tr><th>#</th><th>Date</th><th>Day</th><th>Vehicles/day/station</th><th>Context</th></tr></thead>
            <tbody>
              {data.quietest.map((d, i) => (
                <tr key={d.date}>
                  <td className="rank">{i + 1}</td>
                  <td>{formatDate(d.date)}</td>
                  <td>{d.dow}</td>
                  <td>
                    <div className="bar-cell">
                      <div className="bar quietest-bar" style={{ width: `${(d.avg_per_station / maxVal) * 100}%` }} />
                      <span>{d.avg_per_station.toLocaleString()}</span>
                    </div>
                  </td>
                  <td className="context">{d.context || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
