// « J'envisage d'acheter X » : verdict de cohérence avec le profil. Jamais de conseil d'achat.
import { useId, useState, type FormEvent, type ReactNode } from 'react';
import type { CoherenceResult, Consideration } from '../types/contracts';
import { formatPct, formatSignedPct } from '../lib/format';
import { UNIVERSE, UNIVERSE_BY_TICKER } from '../lib/universe';
import { t } from '../strings';
import { ExplanationView, RuleHits } from './Explanation';
import { ErrorBox } from './Feedback';
import { Term } from './Term';

const VERDICT_ICON = { coherent: '✔', tension: '⚠', incoherent: '✖' } as const;

export function VerdictCard({ result, ticker }: { result: CoherenceResult; ticker?: string }) {
  const m = result.metrics;
  return (
    <div className={`verdict verdict-${result.verdict}`} role="status">
      <p className="verdict-head">
        <span className="verdict-icon" aria-hidden="true">{VERDICT_ICON[result.verdict]}</span>
        <span>{t.consider.verdicts[result.verdict]}{ticker ? ` — ${ticker} à ${formatPct(m.position_weight_after, 0)}` : ''}</span>
      </p>
      <RuleHits hits={result.rule_hits} />
      <h4 className="h-small">{t.consider.metricsTitle}</h4>
      <div className="metric-row">
        <Metric label={<Term id="volatility">{t.consider.vol}</Term>} value={formatPct(m.annualized_vol, 0)} />
        <Metric label={<Term id="max_drawdown">{t.consider.mdd}</Term>} value={formatSignedPct(m.max_drawdown, 0)} bar={Math.abs(m.max_drawdown)} />
        <Metric label={t.consider.worstYear} value={formatSignedPct(m.worst_calendar_year_return, 0)} bar={Math.abs(Math.min(0, m.worst_calendar_year_return))} />
        <Metric label={t.consider.weightAfter} value={formatPct(m.position_weight_after, 0)} />
      </div>
      <ExplanationView explanation={result.explanation} />
    </div>
  );
}

function Metric({ label, value, bar }: { label: ReactNode; value: string; bar?: number }) {
  return (
    <div className="metric">
      <span className="metric-label">{label}</span>
      <span className="metric-value">{value}</span>
      {bar !== undefined && (
        <span className="metric-bar" aria-hidden="true"><span style={{ width: `${Math.min(1, bar) * 100}%` }} /></span>
      )}
    </div>
  );
}

export function ConsiderPanel({
  coherence, busy, error, onSubmit, onClear, current,
}: {
  coherence: CoherenceResult | null;
  busy: boolean;
  error: unknown;
  current: Consideration | null;
  onSubmit: (c: Consideration) => void;
  onClear: () => void;
}) {
  const listId = useId();
  const [ticker, setTicker] = useState(current?.ticker ?? '');
  const [weight, setWeight] = useState(current ? String(Math.round(current.intended_weight * 100)) : '');
  const [formError, setFormError] = useState<string | null>(null);

  function submit(e: FormEvent) {
    e.preventDefault();
    const tk = ticker.trim().toUpperCase();
    const w = Number(weight.replace(',', '.'));
    if (!UNIVERSE_BY_TICKER[tk]) return setFormError(t.consider.unknownTicker);
    if (!Number.isFinite(w) || w < 1 || w > 100) return setFormError(t.consider.invalidWeight);
    setFormError(null);
    onSubmit({ ticker: tk, intended_weight: w / 100 });
  }

  return (
    <section className="panel consider" aria-labelledby="consider-title">
      <h2 id="consider-title">{t.consider.title}</h2>
      <p className="muted small">{t.consider.lead}</p>
      <form className="consider-form" onSubmit={submit} noValidate>
        <label>
          <span>{t.consider.ticker}</span>
          <input list={listId} value={ticker} onChange={(e) => setTicker(e.target.value)} placeholder="NVDA" autoComplete="off" />
          <datalist id={listId}>
            {UNIVERSE.map((a) => <option key={a.ticker} value={a.ticker}>{a.name}</option>)}
          </datalist>
        </label>
        <label>
          <span>{t.consider.weight}</span>
          <input inputMode="decimal" value={weight} onChange={(e) => setWeight(e.target.value)} placeholder="20" />
        </label>
        <div className="consider-actions">
          <button type="submit" className="btn btn-primary" disabled={busy}>{busy ? t.consider.checking : t.consider.submit}</button>
          {current && <button type="button" className="btn btn-ghost" onClick={onClear}>{t.consider.clear}</button>}
        </div>
      </form>
      {formError && <p className="form-error" role="alert">{formError}</p>}
      {error ? <ErrorBox error={error} /> : null}
      {coherence && current && !busy && !error && <VerdictCard result={coherence} ticker={current.ticker} />}
    </section>
  );
}
