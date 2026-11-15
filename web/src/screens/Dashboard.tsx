import { useEffect, useMemo, useState } from 'react';
import { api } from '../api/client';
import { ConsiderPanel } from '../components/ConsiderPanel';
import { EvidenceProvider } from '../components/Evidence';
import { EventsList } from '../components/EventsList';
import { ErrorBox, Skeleton } from '../components/Feedback';
import { NewsCard, categoryLabel } from '../components/NewsCard';
import { PortfolioSummary } from '../components/PortfolioSummary';
import { formatDate } from '../lib/format';
import { useApp } from '../state/store';
import { t } from '../strings';
import type { Consideration, FeedItem, RelevanceLevel } from '../types/contracts';

export function Dashboard() {
  const { profile, portfolio, feed, setFeed } = useApp();
  const [loading, setLoading] = useState(!feed);
  const [error, setError] = useState<unknown>(null);
  const [consideration, setConsideration] = useState<Consideration | null>(null);
  const [considerBusy, setConsiderBusy] = useState(false);
  const [considerError, setConsiderError] = useState<unknown>(null);
  const [fTicker, setFTicker] = useState('');
  const [fCat, setFCat] = useState('');
  const [fLevel, setFLevel] = useState<'' | RelevanceLevel>('');
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!profile || !portfolio || (feed && tick === 0)) return;
    let alive = true;
    setLoading(true);
    setError(null);
    api.buildFeed(profile, portfolio).then(
      (f) => alive && (setFeed(f), setLoading(false)),
      (e: unknown) => alive && (setError(e), setLoading(false)),
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile, portfolio, tick]);

  async function consider(c: Consideration | null) {
    if (!profile || !portfolio) return;
    setConsideration(c);
    setConsiderError(null);
    setConsiderBusy(true);
    try {
      setFeed(await api.buildFeed(profile, portfolio, c));
    } catch (e) {
      setConsiderError(e);
    } finally {
      setConsiderBusy(false);
    }
  }

  const items = feed?.items ?? [];
  const shown = items.filter((i) => i.relevance.shown);
  const hidden = items.filter((i) => !i.relevance.shown);
  const tickers = useMemo(() => [...new Set(items.flatMap((i) => i.tickers))].sort(), [items]);
  const cats = useMemo(() => [...new Set(items.map((i) => i.category))], [items]);
  const filtered = shown.filter(
    (i: FeedItem) =>
      (!fTicker || i.tickers.includes(fTicker)) && (!fCat || i.category === fCat) && (!fLevel || i.relevance.level === fLevel),
  );

  if (!profile || !portfolio) return null;
  if (loading && !feed) return <Skeleton lines={6} label={t.dashboard.loading} />;
  if (error && !feed) return <ErrorBox error={error} onRetry={() => setTick((n) => n + 1)} />;
  if (!feed) return null;

  return (
    <EvidenceProvider evidence={feed.evidence}>
      <div className="dashboard">
        <header className="dash-head">
          <h1>{t.dashboard.title} — {profile.label}</h1>
          <p className="muted small">{t.dashboard.asOf(formatDate(feed.data_as_of), formatDate(feed.news_as_of))}</p>
        </header>
        <PortfolioSummary summary={feed.portfolio_summary} limits={feed.profile.limits} />

        <div className="dash-grid">
          <section className="feed" aria-labelledby="feed-title">
            <h2 id="feed-title">{t.dashboard.feedTitle} <span className="count">{shown.length}</span></h2>
            <div className="filters" role="group" aria-label={t.dashboard.filters}>
              <select aria-label="Filtrer par titre" value={fTicker} onChange={(e) => setFTicker(e.target.value)}>
                <option value="">{t.dashboard.allTickers}</option>
                {tickers.map((tk) => <option key={tk} value={tk}>{tk}</option>)}
              </select>
              <select aria-label="Filtrer par catégorie" value={fCat} onChange={(e) => setFCat(e.target.value)}>
                <option value="">{t.dashboard.allCategories}</option>
                {cats.map((c) => <option key={c} value={c}>{categoryLabel(c)}</option>)}
              </select>
              <select aria-label="Filtrer par niveau" value={fLevel} onChange={(e) => setFLevel(e.target.value as '' | RelevanceLevel)}>
                <option value="">{t.dashboard.allLevels}</option>
                <option value="high">{t.levels.high}</option>
                <option value="medium">{t.levels.medium}</option>
              </select>
            </div>
            {filtered.length === 0 ? <p className="muted">{t.dashboard.feedEmpty}</p> : filtered.map((i) => <NewsCard key={i.news_id} item={i} />)}

            <details className="hidden-section">
              <summary>{t.dashboard.hiddenTitle(feed.hidden.count)}</summary>
              <p className="muted small">{t.dashboard.hiddenLead}</p>
              <ul className="reason-counts">
                {feed.hidden.by_reason.map((r) => (
                  <li key={r.reason}><strong>{r.count}</strong> · {r.reason}</li>
                ))}
              </ul>
              {hidden.map((i) => <NewsCard key={i.news_id} item={i} compact />)}
            </details>
          </section>

          <aside className="side">
            <ConsiderPanel
              coherence={feed.coherence}
              busy={considerBusy}
              error={considerError}
              current={consideration}
              onSubmit={(c) => void consider(c)}
              onClear={() => void consider(null)}
            />
            <section className="panel" aria-labelledby="events-title">
              <h2 id="events-title">{t.dashboard.eventsTitle}</h2>
              <EventsList events={feed.events} />
            </section>
          </aside>
        </div>
      </div>
    </EvidenceProvider>
  );
}
