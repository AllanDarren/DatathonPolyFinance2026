// Onglet « Tester un achat » : la pièce maîtresse. « Avant d'ajouter X : est-ce cohérent avec
// mon objectif, et est-ce que ça diversifie vraiment mon portefeuille? »
// Le verdict vient des règles; les agents rassemblent les preuves; la gouvernance rend les
// contrôles visibles; le gardien vérifie l'explication. Jamais de conseil d'achat.
import { useId, useState, type FormEvent } from 'react';
import { api } from '../api/client';
import {
  AgentTimeline, DiversificationView, GovernanceChecks, InstrumentRisksView, WhatWouldChangeView,
} from '../components/AgentPanels';
import { VerdictCard } from '../components/ConsiderPanel';
import { EvidenceProvider } from '../components/Evidence';
import { ErrorBox, Skeleton } from '../components/Feedback';
import { UNIVERSE, UNIVERSE_BY_TICKER } from '../lib/universe';
import { useApp } from '../state/store';
import { t } from '../strings';
import type { Consideration } from '../types/contracts';

const EXAMPLES: Consideration[] = [
  { ticker: 'NVDA', intended_weight: 0.2 },
  { ticker: 'QQQ', intended_weight: 0.1 },
  { ticker: 'XBB.TO', intended_weight: 0.1 },
  { ticker: 'BTC-USD', intended_weight: 0.05 },
];

export function ConsiderPage() {
  const { profile, portfolio, consideration, considerFeed, setConsiderResult } = useApp();
  const listId = useId();
  const [ticker, setTicker] = useState(consideration?.ticker ?? '');
  const [weight, setWeight] = useState(consideration ? String(Math.round(consideration.intended_weight * 100)) : '');
  const [formError, setFormError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  async function run(c: Consideration) {
    if (!profile || !portfolio) return;
    setTicker(c.ticker);
    setWeight(String(Math.round(c.intended_weight * 100)));
    setBusy(true);
    setError(null);
    try {
      setConsiderResult(c, await api.buildFeed(profile, portfolio, c));
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  function submit(e: FormEvent) {
    e.preventDefault();
    const tk = ticker.trim().toUpperCase();
    const w = Number(weight.replace(',', '.'));
    if (!UNIVERSE_BY_TICKER[tk]) return setFormError(t.consider.unknownTicker);
    if (!Number.isFinite(w) || w < 1 || w > 99) return setFormError(t.consider.invalidWeight);
    setFormError(null);
    void run({ ticker: tk, intended_weight: w / 100 });
  }

  const res = considerFeed?.coherence ?? null;

  return (
    <div className="consider-page">
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
          </div>
        </form>
        <p className="small muted examples">
          {t.consider.examples}{' '}
          {EXAMPLES.map((c) => (
            <button key={c.ticker} type="button" className="chip-btn" disabled={busy} onClick={() => void run(c)}>
              {c.ticker} {Math.round(c.intended_weight * 100)} %
            </button>
          ))}
        </p>
        {formError && <p className="form-error" role="alert">{formError}</p>}
      </section>

      {error ? <ErrorBox error={error} /> : null}
      {busy && <Skeleton lines={5} label={t.consider.agentsWorking} />}

      {res && consideration && !busy && considerFeed && (
        <EvidenceProvider evidence={considerFeed.evidence}>
          <div className="consider-result">
            <div className="consider-main">
              <VerdictCard result={res} ticker={consideration.ticker} />
              {res.what_would_change && (
                <WhatWouldChangeView changes={res.what_would_change} grid={res.weight_grid} current={consideration.intended_weight} />
              )}
              {res.diversification && <DiversificationView d={res.diversification} />}
              {res.instrument_risks && <InstrumentRisksView r={res.instrument_risks} />}
            </div>
            <div className="consider-side">
              {res.governance && <GovernanceChecks governance={res.governance} />}
              {res.agent_trace && res.agent_trace.length > 0 && <AgentTimeline trace={res.agent_trace} />}
            </div>
          </div>
        </EvidenceProvider>
      )}
    </div>
  );
}
