// « Mes nouvelles » : le fil trié par les règles. Trois vues (retenues, toutes, ignorées), un tri,
// des filtres. Les ignorées sont visibles avec leur raison : rien n'est caché sans explication.
import { useMemo, useState } from 'react';
import { NewsCard, categoryLabel } from '../components/NewsCard';
import { t } from '../strings';
import type { FeedItem, FeedResponse, RelevanceLevel } from '../types/contracts';

type View = 'kept' | 'all' | 'hidden';
type Sort = 'relevance' | 'recent';

export function FeedPage({ feed }: { feed: FeedResponse }) {
  const [view, setView] = useState<View>('kept');
  const [sort, setSort] = useState<Sort>('relevance');
  const [fTicker, setFTicker] = useState('');
  const [fCat, setFCat] = useState('');
  const [fLevel, setFLevel] = useState<'' | RelevanceLevel>('');

  const items = feed.items;
  const kept = items.filter((i) => i.relevance.shown);
  const hiddenItems = items.filter((i) => !i.relevance.shown);
  const high = kept.filter((i) => i.relevance.level === 'high');
  const total = kept.length + feed.hidden.count;
  const tickers = useMemo(() => [...new Set(items.flatMap((i) => i.tickers))].sort(), [items]);
  const cats = useMemo(() => [...new Set(items.map((i) => i.category))], [items]);

  const base = view === 'kept' ? kept : view === 'hidden' ? hiddenItems : items;
  const filtered = base
    .filter(
      (i: FeedItem) =>
        (!fTicker || i.tickers.includes(fTicker)) && (!fCat || i.category === fCat) && (!fLevel || i.relevance.level === fLevel),
    )
    .sort((a, b) =>
      sort === 'recent'
        ? b.published_at.localeCompare(a.published_at)
        : Number(b.relevance.shown) - Number(a.relevance.shown) || b.relevance.score - a.relevance.score,
    );

  const VIEWS: { id: View; label: string; n: number }[] = [
    { id: 'kept', label: t.feedPage.kept, n: kept.length },
    { id: 'all', label: t.feedPage.all, n: total },
    { id: 'hidden', label: t.feedPage.hidden, n: feed.hidden.count },
  ];

  return (
    <section className="feed" aria-label={t.dashboard.feedTitle}>
      <p className="funnel mono" aria-label={t.dashboard.funnelLabel}>
        <span><strong>{total}</strong> {t.dashboard.funnelSeen}</span>
        <span aria-hidden="true">→</span>
        <span className="funnel-out"><strong>{feed.hidden.count}</strong> {t.dashboard.funnelHidden}</span>
        <span aria-hidden="true">→</span>
        <span className="funnel-high"><strong>{kept.length}</strong> {t.dashboard.funnelShown}</span>
        <span className="muted">· {high.length} {t.dashboard.funnelHigh}</span>
      </p>

      <div className="feed-bar">
        <div className="segmented" role="group" aria-label={t.feedPage.views}>
          {VIEWS.map((v) => (
            <button key={v.id} type="button" className={`seg-btn ${view === v.id ? 'seg-on' : ''}`} aria-pressed={view === v.id} onClick={() => setView(v.id)}>
              {v.label} <span className="mono">({v.n})</span>
            </button>
          ))}
        </div>
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
            <option value="low">{t.levels.low}</option>
          </select>
          <select aria-label={t.feedPage.sortLabel} value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            <option value="relevance">{t.feedPage.sortRelevance}</option>
            <option value="recent">{t.feedPage.sortRecent}</option>
          </select>
        </div>
      </div>

      {view !== 'kept' && feed.hidden.by_reason.length > 0 && (
        <div className="reason-strip" aria-label={t.dashboard.hiddenLead}>
          <p className="small muted">{t.dashboard.hiddenLead}</p>
          <ul>
            {feed.hidden.by_reason.map((r) => (
              <li key={r.reason}><span className="mono">{r.count}</span> {r.reason}</li>
            ))}
          </ul>
          {feed.hidden.count > hiddenItems.length && (
            <p className="small muted">{t.feedPage.hiddenSample(hiddenItems.length, feed.hidden.count)}</p>
          )}
        </div>
      )}

      <div className="news-list">
        {filtered.length === 0 ? (
          <p className="muted">{t.dashboard.feedEmpty}</p>
        ) : (
          filtered.map((i) => <NewsCard key={i.news_id} item={i} compact={!i.relevance.shown} />)
        )}
      </div>
    </section>
  );
}
