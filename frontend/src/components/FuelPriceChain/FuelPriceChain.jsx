/**
 * FuelPriceChain — oil-to-pump price transmission chart.
 * Shows Brent crude (AUD c/l), Melbourne TGP (wholesale), and VIC retail avg
 * on the same time axis. Demonstrates the ~10-14 day lag from international
 * benchmark to pump price.
 */
import {
  ComposedChart, Line, Area, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer, ReferenceLine,
} from 'recharts';
import { useTrafficData } from '../../hooks/useTrafficData';
import './FuelPriceChain.css';

const CRISIS_DATE = '2026-03-03';

export default function FuelPriceChain() {
  const { data, loading, error } = useTrafficData('/api/fuel/price-chain', { months: 6 });

  if (loading) return <div className="chart-loading">Loading…</div>;
  if (error) return <div className="chart-error">Error: {error}</div>;
  if (!data?.wholesale?.length) return <div className="chart-empty">No data</div>;

  // Merge wholesale and retail into unified chart data by date
  const retailMap = {};
  (data.retail || []).forEach(r => { retailMap[r.date] = r.avg_u91_cpl; });

  const chartData = data.wholesale.map(w => ({
    date: w.date,
    label: new Date(w.date + 'T00:00:00').toLocaleDateString('en-AU', { day: 'numeric', month: 'short' }),
    brent: w.brent_aud_cpl,
    tgp: w.mel_tgp_cpl,
    retail: retailMap[w.date] || null,
  }));

  return (
    <div className="price-chain">
      <div className="price-chain-header">
        <span className="price-chain-note">
          Brent crude → Melbourne wholesale (TGP) → VIC retail pump. ~10–14 day lag from international to pump.
        </span>
      </div>
      <ResponsiveContainer width="100%" height={360}>
        <ComposedChart data={chartData} margin={{ top: 5, right: 20, bottom: 5, left: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis
            dataKey="label"
            tick={{ fontSize: 11, fill: 'var(--color-text-secondary)' }}
            interval={Math.floor(chartData.length / 8)}
          />
          <YAxis
            tick={{ fontSize: 11, fill: 'var(--color-text-secondary)' }}
            label={{ value: 'c/litre', angle: -90, position: 'insideLeft', style: { fontSize: 11 } }}
          />
          <Tooltip
            contentStyle={{ background: 'var(--color-bg)', border: '1px solid var(--color-border)', fontSize: 12 }}
            formatter={(val, name) => val ? [`${val.toFixed(1)}c`, name] : ['-', name]}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine
            x={chartData.find(d => d.date >= CRISIS_DATE)?.label}
            stroke="#E24B4A" strokeDasharray="4 4" strokeWidth={1}
            label={{ value: 'Strait of Hormuz', position: 'top', fontSize: 10, fill: '#E24B4A' }}
          />
          <Area
            type="monotone" dataKey="brent" name="Brent crude (AUD c/l)"
            stroke="#E9C46A" fill="#E9C46A" fillOpacity={0.15} strokeWidth={1.5}
            dot={false} connectNulls
          />
          <Line
            type="monotone" dataKey="tgp" name="Melbourne TGP (wholesale)"
            stroke="#F4A261" strokeWidth={2} dot={false} connectNulls
          />
          <Line
            type="monotone" dataKey="retail" name="VIC retail avg (U91)"
            stroke="#E24B4A" strokeWidth={2.5} dot={{ r: 3, fill: '#E24B4A' }}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
