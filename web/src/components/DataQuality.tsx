// Qualité des données : chaque série passe par les mêmes contrôles avant tout calcul (core/quality.py).
import type { QualityReport } from '../types/contracts';
import { formatDate } from '../lib/format';
import { t } from '../strings';
import { EvidenceChip } from './Evidence';

const ICON = { ok: '✔', warning: '⚠', blocking: '✖' } as const;

export function QualityBadge({ q }: { q: QualityReport }) {
  return (
    <span className={`badge q-${q.status}`} title={t.quality.status[q.status]}>
      <span aria-hidden="true">{ICON[q.status]} </span>
      {q.origin === 'on_demand' ? t.consider.onDemand : t.consider.verified}
    </span>
  );
}

export function DataQualityView({ q }: { q: QualityReport }) {
  return (
    <section className="panel" aria-labelledby={`q-${q.ticker}`}>
      <h2 id={`q-${q.ticker}`} className="h-panel">
        {t.quality.title} — {q.ticker} <QualityBadge q={q} />
      </h2>
      <p className={`div-verdict q-box-${q.status}`}>
        <span aria-hidden="true">{ICON[q.status]} </span>
        <strong>{t.quality.status[q.status]}</strong>
        {q.first_date && q.last_date && <> — {t.quality.coverage(q.n_obs, formatDate(q.first_date), formatDate(q.last_date))}</>}
      </p>
      <dl className="facts">
        <div><dt>{t.evidence.source}</dt><dd>{q.origin === 'on_demand' ? q.source : `${t.quality.starter} (${q.source})`}</dd></div>
        {q.reference_calendar && <div><dt>{t.quality.calendar}</dt><dd>{q.reference_calendar}</dd></div>}
      </dl>
      {q.warnings_fr.length > 0 && (
        <ul className="plain small">{q.warnings_fr.map((w, i) => <li key={i}><span aria-hidden="true">⚠ </span>{w}</li>)}</ul>
      )}
      {q.notes_fr.length > 0 && (
        <>
          <h3 className="h-small">{t.quality.notes}</h3>
          <ul className="plain small muted">{q.notes_fr.map((w, i) => <li key={i}>{w}</li>)}</ul>
        </>
      )}
      <EvidenceChip id={q.evidence_id} />
    </section>
  );
}

export function PositionsQuality({ reports }: { reports: QualityReport[] }) {
  return (
    <section className="panel" aria-labelledby="pq-title">
      <h2 id="pq-title" className="h-panel">{t.quality.positionsTitle}</h2>
      <p className="muted small">{t.quality.positionsLead}</p>
      <table className="table compact">
        <tbody>
          {reports.map((q) => (
            <tr key={q.ticker}>
              <th scope="row" className="ticker">{q.ticker}</th>
              <td><span className={`q-dot q-${q.status}`} aria-hidden="true">{ICON[q.status]}</span> {t.quality.status[q.status]}</td>
              <td className="small muted">{[...q.warnings_fr, ...q.notes_fr].join(' ') || '—'}</td>
              <td><EvidenceChip id={q.evidence_id} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
