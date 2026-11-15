// Couche multi-agents rendue visible : trace des agents, contrôles de gouvernance,
// diversification, risques du type d'instrument et « ce qui changerait la réponse ».
// Aucun calcul ici : tout vient de l'API (CoherenceResult v0.3.0).
import type {
  DiversificationImpact, Governance, GovernanceControl, InstrumentProfile, ToolCall, Verdict, WeightGridPoint,
  WhatWouldChange,
} from '../types/contracts';
import { formatNum, formatPct } from '../lib/format';
import { t } from '../strings';
import { EvidenceChip } from './Evidence';

const A = t.agents;

export function AgentTimeline({ trace }: { trace: ToolCall[] }) {
  return (
    <section className="panel" aria-labelledby="trace-title">
      <h2 id="trace-title" className="h-panel">{A.traceTitle}</h2>
      <p className="muted small">{A.traceLead}</p>
      <ol className="timeline">
        {trace.map((s) => (
          <li key={s.step} className={`tl-step tl-${s.status} ${s.planner === 'code' ? 'tl-code' : ''}`}>
            <span className="tl-dot" aria-hidden="true">{s.status === 'error' ? '✖' : s.step}</span>
            <div className="tl-body">
              <p className="tl-title">
                <strong>{A.tools[s.tool] ?? s.tool}</strong>
                <span className="tl-who">
                  {s.planner === 'code' ? A.byCode : s.forced ? A.forced : s.planner === 'mock' ? A.byPlan : A.byModel(s.planner)}
                </span>
              </p>
              {s.status === 'error' && s.error && <p className="small warn">{s.error}</p>}
              {s.evidence_ids.length > 0 && (
                <span className="claim-evidence">{s.evidence_ids.map((id) => <EvidenceChip key={id} id={id} />)}</span>
              )}
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

const CONTROL_ICON: Record<GovernanceControl['status'], string> = { ok: '✔', warning: '⚠', fail: '✖', info: 'ⓘ' };

export function GovernanceChecks({ governance }: { governance: Governance }) {
  return (
    <section className="panel" aria-labelledby="gov-title">
      <h2 id="gov-title" className="h-panel">{A.governanceTitle}</h2>
      <p className="muted small">{A.governanceLead}</p>
      <ul className="controls">
        {governance.controls.map((c) => (
          <li key={c.id} className={`control control-${c.status}`}>
            <span className="control-icon" aria-hidden="true">{CONTROL_ICON[c.status]}</span>
            <div>
              <p className="control-label">
                <strong>{c.label_fr}</strong> <span className="sr-only">({A.status[c.status]})</span>
              </p>
              <p className="small">{c.detail_fr}</p>
              {c.evidence_ids.length > 0 && (
                <span className="claim-evidence">{c.evidence_ids.map((id) => <EvidenceChip key={id} id={id} />)}</span>
              )}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}

const DIV_ICON = { new_exposure: '✔', partial: '◐', overlap: '⚠' } as const;

function ExposureBars({ before, after, labels }: { before: Record<string, number>; after: Record<string, number>; labels?: Record<string, string> }) {
  const keys = [...new Set([...Object.keys(before), ...Object.keys(after)])].sort((a, b) => (after[b] ?? 0) - (after[a] ?? 0));
  return (
    <table className="table compact exposure">
      <thead>
        <tr><th scope="col" /><th scope="col" className="num">{A.before}</th><th scope="col" className="num">{A.after}</th></tr>
      </thead>
      <tbody>
        {keys.map((k) => (
          <tr key={k}>
            <th scope="row">{labels?.[k] ?? k}</th>
            <td className="num">{formatPct(before[k] ?? 0, 0)}</td>
            <td className="num"><strong>{formatPct(after[k] ?? 0, 0)}</strong></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function DiversificationView({ d }: { d: DiversificationImpact }) {
  const top = d.correlations.slice(0, 4);
  return (
    <section className="panel" aria-labelledby="div-title">
      <h2 id="div-title" className="h-panel">{A.diversificationTitle}</h2>
      <p className={`div-verdict div-${d.verdict}`}>
        <span aria-hidden="true">{DIV_ICON[d.verdict]} </span>
        <strong>{A.divVerdicts[d.verdict]}</strong> — {d.text_fr}
      </p>
      <div className="two-col">
        <div>
          <h3 className="h-small">{A.assetClasses}</h3>
          <ExposureBars before={d.asset_class_before} after={d.asset_class_after} labels={t.labels.assetClass} />
        </div>
        <div>
          <h3 className="h-small">{A.currencies}</h3>
          <ExposureBars before={d.currency_before} after={d.currency_after} />
        </div>
      </div>
      {top.length > 0 && (
        <>
          <h3 className="h-small">{A.correlationsTitle}</h3>
          <ul className="corr-list">
            {top.map((c) => (
              <li key={c.ticker}>
                <span className="ticker">{c.ticker}</span>
                <span className="corr-bar" aria-hidden="true"><span style={{ width: `${Math.max(0, c.correlation) * 100}%` }} /></span>
                <span className="num">{formatNum(c.correlation)}</span>
                <EvidenceChip id={c.evidence_id} />
              </li>
            ))}
          </ul>
          <p className="muted small">{A.correlationNote}</p>
        </>
      )}
    </section>
  );
}

export function InstrumentRisksView({ r }: { r: InstrumentProfile }) {
  return (
    <section className="panel" aria-labelledby="inst-title">
      <h2 id="inst-title" className="h-panel">{A.instrumentTitle(r.ticker, r.label_fr)}</h2>
      <dl className="facts">
        <div><dt>{A.whatYouOwn}</dt><dd>{r.what_you_own_fr}</dd></div>
        <div><dt>{A.returnSource}</dt><dd>{r.return_source_fr}</dd></div>
      </dl>
      <ul className="risk-list">
        {r.risks.map((x) => (
          <li key={x.risk} className={`risk risk-${x.level}`}>
            <span className={`risk-level lvl-${x.level}`}>{A.levels[x.level]}</span>
            <div>
              <strong>{x.label_fr}</strong> <span className="muted small">— {x.question_fr}</span>
              <p className="small">{x.text_fr}</p>
            </div>
          </li>
        ))}
      </ul>
      <p className="muted small">{A.source} : <code>{r.source}</code></p>
    </section>
  );
}

const VERDICT_SHORT: Record<Verdict, string> = { coherent: '✔', tension: '⚠', incoherent: '✖' };

/** Bande de poids : verdict des MÊMES règles pour chaque poids testé (calculé par le serveur). */
export function WeightStrip({ grid, current }: { grid: WeightGridPoint[]; current: number }) {
  const shown = grid.filter((g) => g.weight <= 0.3 + 1e-9 || Math.abs(g.weight - current) < 1e-9);
  return (
    <figure className="weight-strip">
      <div className="ws-cells" role="list" aria-label={A.stripLabel}>
        {shown.map((g) => {
          const isCurrent = Math.abs(g.weight - current) < 1e-9;
          return (
            <span
              key={g.weight}
              role="listitem"
              className={`ws-cell ws-${g.verdict} ${isCurrent ? 'ws-current' : ''}`}
              title={`${formatPct(g.weight, 0)} : ${t.consider.verdicts[g.verdict]}${g.rule_ids.length ? ` (${g.rule_ids.join(', ')})` : ''}`}
              aria-label={`${formatPct(g.weight, 0)} : ${t.consider.verdicts[g.verdict]}`}
            >
              {isCurrent ? VERDICT_SHORT[g.verdict] : ''}
            </span>
          );
        })}
      </div>
      <figcaption className="ws-axis small muted">
        <span>{formatPct(shown[0]?.weight ?? 0, 0)}</span>
        <span>{A.stripCaption}</span>
        <span>{formatPct(shown[shown.length - 1]?.weight ?? 0, 0)}</span>
      </figcaption>
      <ul className="ws-legend small">
        <li><span className="ws-cell ws-coherent" aria-hidden="true" /> {t.consider.verdicts.coherent}</li>
        <li><span className="ws-cell ws-tension" aria-hidden="true" /> {t.consider.verdicts.tension}</li>
        <li><span className="ws-cell ws-incoherent" aria-hidden="true" /> {t.consider.verdicts.incoherent}</li>
      </ul>
    </figure>
  );
}

export function WhatWouldChangeView({ changes, grid, current }: { changes: WhatWouldChange[]; grid?: WeightGridPoint[] | null; current: number }) {
  return (
    <section className="panel" aria-labelledby="wwc-title">
      <h2 id="wwc-title" className="h-panel">{A.wwcTitle}</h2>
      <p className="muted small">{A.wwcLead}</p>
      {grid && grid.length > 0 && <WeightStrip grid={grid} current={current} />}
      {changes.length === 0 ? (
        <p className="small">{A.wwcNone}</p>
      ) : (
        <ul className="wwc-list">
          {changes.map((c, i) => (
            <li key={i} className={`wwc wwc-${c.kind}`}>
              <span className="wwc-kind">{c.kind === 'weight' ? A.wwcWeight : A.wwcProfile}</span>
              <span>{c.text_fr}</span>
              <EvidenceChip id={c.evidence_id} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
