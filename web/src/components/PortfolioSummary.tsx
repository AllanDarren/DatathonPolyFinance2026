import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts';
import type { FeedResponse } from '../types/contracts';
import { formatCad, formatPct } from '../lib/format';
import { t } from '../strings';
import { Term } from './Term';

// Palette limitée, une couleur par catégorie d'actif (toujours accompagnée du libellé).
export const CLASS_COLORS: Record<string, string> = {
  equity_ca: '#1f4e79',
  equity_us: '#4a7fb5',
  equity_etf: '#8fb3d9',
  bond_etf: '#3f8f6b',
  gold_etf: '#c9a227',
  crypto: '#b5523b',
};

export function PortfolioSummary({ summary, limits }: { summary: FeedResponse['portfolio_summary']; limits: FeedResponse['profile']['limits'] }) {
  const data = Object.entries(summary.asset_class_weights)
    .filter(([, w]) => w > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([k, w]) => ({ key: k, name: t.labels.assetClass[k] ?? k, value: w }));
  const highVolOver = summary.high_vol_share > limits.max_high_vol_share;

  return (
    <section className="panel summary" aria-labelledby="sum-title">
      <h2 id="sum-title">{t.dashboard.summaryTitle}</h2>
      <div className="summary-grid">
        <figure className="ring">
          <ResponsiveContainer width="100%" height={180}>
            <PieChart>
              <Pie data={data} dataKey="value" nameKey="name" innerRadius={52} outerRadius={80} paddingAngle={1} isAnimationActive={false}>
                {data.map((d) => <Cell key={d.key} fill={CLASS_COLORS[d.key] ?? '#888'} />)}
              </Pie>
              <Tooltip formatter={(v: number) => formatPct(v)} />
            </PieChart>
          </ResponsiveContainer>
          <figcaption className="sr-only">{t.dashboard.weightsRing}</figcaption>
          <ul className="legend">
            {data.map((d) => (
              <li key={d.key}>
                <span className="swatch" style={{ background: CLASS_COLORS[d.key] ?? '#888' }} aria-hidden="true" />
                {d.name} <strong>{formatPct(d.value)}</strong>
              </li>
            ))}
          </ul>
        </figure>
        <div className="summary-side">
          <div className="kpis">
            <div className="kpi">
              <span className="kpi-label"><Term id="concentration">{t.dashboard.concentration}</Term></span>
              <span className="kpi-value">{formatPct(summary.top3_concentration)}</span>
            </div>
            <div className={`kpi ${highVolOver ? 'kpi-warn' : ''}`}>
              <span className="kpi-label"><Term id="volatility">{t.dashboard.highVolShare}</Term></span>
              <span className="kpi-value">
                {highVolOver && <span aria-hidden="true">⚠ </span>}
                {formatPct(summary.high_vol_share)}
              </span>
              <span className="kpi-sub">limite du profil : {formatPct(limits.max_high_vol_share, 0)}</span>
            </div>
          </div>
          <h3 className="h-small">{t.dashboard.topPositions}</h3>
          <table className="table compact">
            <tbody>
              {summary.top_positions.map((p) => (
                <tr key={p.ticker}>
                  <td className="ticker">{p.ticker}</td>
                  <td className="num">{formatCad(p.amount)}</td>
                  <td className="num">{formatPct(p.weight)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
