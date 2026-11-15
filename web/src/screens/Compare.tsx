// Vue « Comparer deux profils » : même journée de nouvelles, deux profils côte à côte.
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { VerdictCard } from '../components/ConsiderPanel';
import { EvidenceProvider } from '../components/Evidence';
import { ErrorBox, Skeleton } from '../components/Feedback';
import { NewsCard } from '../components/NewsCard';
import { formatPct } from '../lib/format';
import { useAsync } from '../lib/useAsync';
import { UNIVERSE } from '../lib/universe';
import { useApp } from '../state/store';
import { t } from '../strings';
import type { Consideration, FeedResponse, Persona, Portfolio } from '../types/contracts';

type Side = { feed: FeedResponse; persona: Persona };

export function Compare() {
  const { portfolio: currentPortfolio, persona: currentPersona } = useApp();
  const personas = useAsync(() => api.getPersonas(), []);
  const [leftId, setLeftId] = useState(currentPersona?.id ?? 'robert');
  const [rightId, setRightId] = useState(currentPersona?.id === 'amira' ? 'robert' : 'amira');
  const [samePortfolio, setSamePortfolio] = useState(false);
  const [considerTicker, setConsiderTicker] = useState('NVDA');
  const [considerWeight, setConsiderWeight] = useState('20');
  const [useConsider, setUseConsider] = useState(true);
  const [sides, setSides] = useState<[Side, Side] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    const list = personas.data;
    if (!list) return;
    const left = list.find((p) => p.id === leftId);
    const right = list.find((p) => p.id === rightId);
    if (!left || !right) return;
    const w = Number(considerWeight.replace(',', '.'));
    const consideration: Consideration | null =
      useConsider && considerTicker && Number.isFinite(w) && w > 0 ? { ticker: considerTicker, intended_weight: w / 100 } : null;

    let alive = true;
    setLoading(true);
    setError(null);
    const portfolioFor = async (p: Persona): Promise<Portfolio> =>
      samePortfolio && currentPortfolio ? currentPortfolio : api.parsePortfolio(p.sample_portfolio_csv);
    Promise.all(
      [left, right].map(async (p) => ({ persona: p, feed: await api.buildFeed(p.profile, await portfolioFor(p), consideration) })),
    ).then(
      (res) => alive && (setSides([res[0]!, res[1]!]), setLoading(false)),
      (e: unknown) => alive && (setError(e), setLoading(false)),
    );
    return () => {
      alive = false;
    };
  }, [personas.data, leftId, rightId, samePortfolio, currentPortfolio, useConsider, considerTicker, considerWeight]);

  if (personas.loading) return <Skeleton lines={4} label="Chargement des profils…" />;
  if (personas.error) return <ErrorBox error={personas.error} onRetry={personas.reload} />;
  const list = personas.data ?? [];

  const swap = () => {
    setLeftId(rightId);
    setRightId(leftId);
  };

  return (
    <div className="compare">
      <header className="dash-head">
        <h2>{t.compare.title}</h2>
        <p className="lead">{t.compare.lead}</p>
      </header>
      <div className="panel compare-controls">
        <label>
          <span>{t.compare.left}</span>
          <select value={leftId} onChange={(e) => setLeftId(e.target.value)}>
            {list.map((p) => <option key={p.id} value={p.id}>{p.profile.label}</option>)}
          </select>
        </label>
        <button type="button" className="btn btn-secondary" onClick={swap} aria-label="Inverser les deux profils">⇄</button>
        <label>
          <span>{t.compare.right}</span>
          <select value={rightId} onChange={(e) => setRightId(e.target.value)}>
            {list.map((p) => <option key={p.id} value={p.id}>{p.profile.label}</option>)}
          </select>
        </label>
        <label className="check">
          <input type="checkbox" checked={samePortfolio} disabled={!currentPortfolio} onChange={(e) => setSamePortfolio(e.target.checked)} />
          <span>{t.compare.samePortfolio}</span>
        </label>
        <label className="check">
          <input type="checkbox" checked={useConsider} onChange={(e) => setUseConsider(e.target.checked)} />
          <span>{t.compare.consider}</span>
        </label>
        {useConsider && (
          <>
            <select aria-label={t.consider.ticker} value={considerTicker} onChange={(e) => setConsiderTicker(e.target.value)}>
              {UNIVERSE.map((a) => <option key={a.ticker} value={a.ticker}>{a.ticker}</option>)}
            </select>
            <label className="inline">
              <input className="w-num" inputMode="decimal" aria-label={t.consider.weight} value={considerWeight} onChange={(e) => setConsiderWeight(e.target.value)} />
              <span>%</span>
            </label>
          </>
        )}
      </div>

      {error ? <ErrorBox error={error} /> : null}
      {loading && !sides && <Skeleton lines={6} label={t.dashboard.loading} />}
      {sides && (
        <div className={`compare-grid ${loading ? 'is-loading' : ''}`} aria-busy={loading}>
          {sides.map((s) => <CompareColumn key={s.persona.id} side={s} />)}
        </div>
      )}
    </div>
  );
}

function CompareColumn({ side }: { side: Side }) {
  const { feed, persona } = side;
  const p = feed.profile;
  const shown = feed.items.filter((i) => i.relevance.shown);
  return (
    <EvidenceProvider evidence={feed.evidence}>
      <section className="panel compare-col" aria-label={p.label}>
        <h2>{p.label}</h2>
        <p className="muted small">{persona.label}</p>
        <ul className="chips">
          <li>{t.profile.horizon} : {t.profile.horizonValue(p.horizon_years)}</li>
          <li>{t.profile.risk} : {t.labels.risk[p.risk_tolerance]}</li>
          <li>{t.profile.maxLoss} : {formatPct(p.max_acceptable_loss_pct, 0)}</li>
          {p.preferences.avoid_controversies && <li>{t.profile.avoidControversies}</li>}
        </ul>
        {feed.coherence && <VerdictCard result={feed.coherence} />}
        {feed.coherence?.what_would_change?.[0] && (
          <p className="small callout">{feed.coherence.what_would_change[0].text_fr}</p>
        )}
        {feed.coherence?.diversification && (
          <p className="small"><strong>{t.agents.diversificationTitle} :</strong> {feed.coherence.diversification.text_fr}</p>
        )}
        <h3 className="h-small">
          {shown.length} {t.compare.shown} · {feed.hidden.count} {t.compare.hidden}
        </h3>
        {shown.map((i) => <NewsCard key={i.news_id} item={i} compact />)}
      </section>
    </EvidenceProvider>
  );
}
