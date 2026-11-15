// Distribution des mouvements passés (p10, médiane, p90) et cas passés. Limites toujours visibles.
import { Bar, BarChart, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import type { HistoricalContext } from '../types/contracts';
import { formatDate, formatPct, formatSignedPct } from '../lib/format';
import { t } from '../strings';
import { EvidenceChip } from './Evidence';

export function RangeBar({ p10, median, p90 }: { p10: number; median: number; p90: number }) {
  // Échelle symétrique autour de 0 pour placer les repères (mise en page seulement).
  const span = Math.max(Math.abs(p10), Math.abs(p90), 0.0001) * 1.15;
  const pos = (v: number) => `${((v + span) / (2 * span)) * 100}%`;
  return (
    <div className="range" role="img" aria-label={`p10 ${formatSignedPct(p10)}, médiane ${formatSignedPct(median)}, p90 ${formatSignedPct(p90)}`}>
      <div className="range-track" />
      <div className="range-zero" style={{ left: pos(0) }} />
      <div className="range-band" style={{ left: pos(p10), width: `calc(${pos(p90)} - ${pos(p10)})` }} />
      <div className="range-median" style={{ left: pos(median) }} />
      <span className="range-lbl" style={{ left: pos(p10) }}>{formatSignedPct(p10)}</span>
      <span className="range-lbl range-lbl-med" style={{ left: pos(median) }}>{formatSignedPct(median)}</span>
      <span className="range-lbl" style={{ left: pos(p90) }}>{formatSignedPct(p90)}</span>
    </div>
  );
}

export function HistoricalContextView({ ctx }: { ctx: HistoricalContext }) {
  const data = ctx.events.map((e) => ({ date: e.date, label: formatDate(e.date), ret: e.return }));
  return (
    <section className="history">
      <h4>
        {t.history.title} — {ctx.asset} <EvidenceChip id={ctx.evidence_id} />
      </h4>
      <div className="history-stats">
        <div className="stat"><span className="stat-label">{t.history.nEvents(ctx.n_events)}</span></div>
        <div className="stat"><span className="stat-label">{t.history.median}</span><span className="stat-value">{formatSignedPct(ctx.median_return)}</span></div>
        <div className="stat"><span className="stat-label">{t.history.sharePositive}</span><span className="stat-value">{formatPct(ctx.share_positive, 0)}</span></div>
        <div className="stat"><span className="stat-label">{t.history.window}</span><span className="stat-value small">{ctx.window}</span></div>
      </div>
      <p className="small muted">{t.history.range}</p>
      <RangeBar p10={ctx.p10} median={ctx.median_return} p90={ctx.p90} />
      {data.length > 0 && (
        <>
          <p className="small muted">{t.history.cases}</p>
          <div className="chart-sm">
            <ResponsiveContainer width="100%" height={140}>
              <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                <XAxis dataKey="date" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={(v: number) => formatPct(v, 0)} tick={{ fontSize: 11 }} width={48} />
                <ReferenceLine y={0} stroke="var(--line-strong)" />
                <Tooltip formatter={(v: number) => formatSignedPct(v)} labelFormatter={(l: string) => formatDate(l)} />
                <Bar dataKey="ret" name="Mouvement" isAnimationActive={false}>
                  {data.map((d) => <Cell key={d.date} fill={d.ret >= 0 ? 'var(--pos)' : 'var(--neg)'} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
      <div className="caveats">
        <strong>{t.history.caveats}</strong>
        <ul>
          {ctx.caveats.map((c, i) => <li key={i}>{c}</li>)}
        </ul>
        <p className="small"><strong>{t.history.notForecast}</strong></p>
      </div>
    </section>
  );
}
