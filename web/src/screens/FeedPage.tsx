// Onglet « Mes nouvelles » : le fil trié par les règles, avec les nouvelles masquées et leur raison.
import { useMemo, useState } from 'react';
import { NewsCard, categoryLabel } from '../components/NewsCard';
import { t } from '../strings';
import type { FeedItem, FeedResponse, RelevanceLevel } from '../types/contracts';

export function FeedPage({ feed }: { feed: FeedResponse }) {
  const [fTicker, setFTicker] = useState('');
  const [fCat, setFCat] = useState('');
  const [fLevel, setFLevel] = useState<'' | RelevanceLevel>('');

  const items = feed.items;
  const shown = items.filter((i) => i.relevance.shown);
  const tickers = useMemo(() => [...new Set(items.flatMap((i) => i.tickers))].sort(), [items]);
  const cats = useMemo(() => [...new Set(items.map((i) => i.category))], [items]);
  const filtered = shown.filter(
    (i: FeedItem) =>
      (!fTicker || i.tickers.includes(fTicker)) && (!fCat || i.category === fCat) && (!fLevel || i.relevance.level === fLevel),
  );
  const high = shown.filter((i) => i.relevance.level === 'high');

  return (
    <section className="feed" aria-labelledby="feed-title">
      <div className="feed-intro panel">
        <h2 id="feed-title">{t.dashboard.feedTitle}</h2>
        <p className="funnel" aria-label={t.dashboard.funnelLabel}>
          <span><strong>{shown.length + feed.hidden.count}</strong> {t.dashboard.funnelSeen}</span>
          <span aria-hidden="true">→</span>
          <span><strong>{feed.hidden.count}</strong> {t.dashboard.funnelHidden}</span>
          <span aria-hidden="true">→</span>
          <span><strong>{shown.length}</strong> {t.dashboard.funnelShown}</span>
          <span aria-hidden="true">→</span>
          <span className="funnel-high"><strong>{high.length}</strong> {t.dashboard.funnelHigh}</span>
        </p>
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
        {items.filter((i) => !i.relevance.shown).map((i) => <NewsCard key={i.news_id} item={i} compact />)}
      </details>
    </section>
  );
}
