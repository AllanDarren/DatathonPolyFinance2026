// Carte de nouvelle allégée : un seul badge de niveau, la raison principale en une ligne,
// et le « Pourquoi? » dans un tiroir latéral (règles, preuves, gardien, contexte historique).
import { useEffect, useRef, useState } from 'react';
import type { FeedItem, RelevanceLevel, RuleHit } from '../types/contracts';
import { formatDate, formatPct } from '../lib/format';
import { t } from '../strings';
import { ExplanationView, RuleHits } from './Explanation';
import { SyntheticBadge } from './Feedback';
import { HistoricalContextView } from './HistoricalContext';
import { Term } from './Term';

const LEVEL_ICON: Record<RelevanceLevel, string> = { high: '▲', medium: '●', low: '▽' };

export function RelevanceBadge({ level }: { level: RelevanceLevel; score?: number }) {
  return (
    <span className={`badge level-${level}`}>
      <span aria-hidden="true">{LEVEL_ICON[level]}</span> {t.card.relevance} {t.levels[level].toLowerCase()}
    </span>
  );
}

export function categoryLabel(id: string) {
  return t.labels.categories[id] ?? id;
}

/** Raison principale : la règle qui a le plus fait monter le score (hors poids de base de la catégorie). */
export function mainReason(item: FeedItem): string {
  const hits = item.relevance.rule_hits;
  const boosts = hits.filter((h: RuleHit) => !h.rule_id.startsWith('R_BASE_') && (h.delta ?? 0) > 0);
  const best = boosts.sort((a, b) => (b.delta ?? 0) - (a.delta ?? 0))[0];
  if (best) return best.text;
  if (item.linked_ticker && item.relevance.position_weight > 0) {
    return t.card.weightReason(item.linked_ticker, formatPct(item.relevance.position_weight, 0));
  }
  return hits[0]?.text ?? '';
}

function SourceTierBadge({ item }: { item: FeedItem }) {
  const tier = item.source_tier;
  if (!tier || tier.id === 'established' || tier.id === 'unknown') return null;
  return (
    <span className={`badge tier-${tier.id}`} title={tier.text_fr}>
      <span aria-hidden="true">{tier.id === 'primary' ? '◆ ' : '◇ '}</span>
      {tier.label_fr}
    </span>
  );
}

export function NewsCard({ item, compact = false }: { item: FeedItem; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const reason = mainReason(item);
  const n = item.cluster?.size ?? 1;
  return (
    <article className={`news-card rel-${item.relevance.level} ${item.relevance.shown ? '' : 'news-card-hidden'} ${compact ? 'news-card-compact' : ''}`}>
      <header className="news-head">
        {item.tickers.slice(0, 4).map((tk) => <span key={tk} className="ticker">{tk}</span>)}
        <RelevanceBadge level={item.relevance.level} />
        {item.is_synthetic && <SyntheticBadge />}
        <SourceTierBadge item={item} />
        {n > 1 && <span className="badge badge-cluster" title={item.cluster?.sources.join(', ')}>{t.card.sources(n)}</span>}
        <time className="news-time mono" dateTime={item.published_at}>{formatDate(item.published_at)}</time>
      </header>
      <h3 className="news-title">{item.title}</h3>
      {reason && item.relevance.shown && (
        <p className="news-reason"><span aria-hidden="true">→ </span><span className="sr-only">{t.card.whyHere} </span>{reason}</p>
      )}
      {!item.relevance.shown && item.explanation.summary && (
        <p className="news-hidden-reason"><span aria-hidden="true">⦸ </span>{item.explanation.summary}</p>
      )}
      <div className="news-foot">
        <p className="news-meta">
          <span>{item.source}</span> · <span>{categoryLabel(item.category)}</span> · <span>{t.horizonRelevance[item.horizon_relevance]}</span>
        </p>
        <div className="news-actions">
          <button type="button" className="btn btn-why" aria-haspopup="dialog" onClick={() => setOpen(true)}>
            {t.card.why}
          </button>
          <a className="btn btn-ghost" href={item.url} target="_blank" rel="noreferrer noopener">
            {t.card.openSource} <span aria-hidden="true">↗</span>
          </a>
        </div>
      </div>
      {open && <WhyDrawer item={item} onClose={() => setOpen(false)} />}
    </article>
  );
}

function WhyDrawer({ item, onClose }: { item: FeedItem; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);
  const r = item.relevance;
  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer drawer-wide" role="dialog" aria-modal="true" aria-label={t.card.whyTitle} onClick={(e) => e.stopPropagation()}>
        <header className="drawer-head">
          <h2>{t.card.whyTitle}</h2>
          <button ref={closeRef} type="button" className="btn btn-ghost" onClick={onClose}>{t.card.closeWhy}</button>
        </header>
        <p className="why-headline">{item.title}</p>
        <p className="small muted">
          <RelevanceBadge level={r.level} /> {t.card.score(r.score.toFixed(2))} · {categoryLabel(item.category)} ·{' '}
          {t.horizonRelevance[item.horizon_relevance]}
        </p>

        <h3 className="h-small">{t.card.rulesTitle}</h3>
        <RuleHits hits={r.rule_hits} />
        <p className="small">
          <Term id="concentration">{t.card.positionWeight}</Term>
          {item.linked_ticker ? ` (${item.linked_ticker})` : ''} : <strong>{formatPct(r.position_weight)}</strong>
        </p>

        <h3 className="h-small">{t.card.claimsTitle}</h3>
        <ExplanationView explanation={item.explanation} />

        {item.historical_context && <HistoricalContextView ctx={item.historical_context} />}

        <h3 className="h-small">{t.card.sourceTitle}</h3>
        <ul className="small plain">
          <li>
            {item.source}
            {item.source_tier ? ` — ${item.source_tier.label_fr}. ${item.source_tier.text_fr}` : ''}
          </li>
          {item.mention === 'none' && <li>{t.card.mentionNone}</li>}
          {(item.cluster?.size ?? 1) > 1 && <li>{t.card.clusterSources(item.cluster!.sources.join(', '))}</li>}
        </ul>
      </aside>
    </div>
  );
}
