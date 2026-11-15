import { useId, useState } from 'react';
import type { FeedItem, RelevanceLevel } from '../types/contracts';
import { formatDate, formatPct } from '../lib/format';
import { t } from '../strings';
import { ExplanationView, RuleHits } from './Explanation';
import { SyntheticBadge } from './Feedback';
import { HistoricalContextView } from './HistoricalContext';
import { Term } from './Term';

const LEVEL_ICON: Record<RelevanceLevel, string> = { high: '▲', medium: '●', low: '▽' };

export function RelevanceBadge({ level, score }: { level: RelevanceLevel; score: number }) {
  return (
    <span className={`badge level-${level}`} title={`${t.card.relevance} : ${score.toFixed(2)}`}>
      <span aria-hidden="true">{LEVEL_ICON[level]}</span> {t.card.relevance} {t.levels[level].toLowerCase()}
      <span className="badge-score">{score.toFixed(2)}</span>
    </span>
  );
}

export function categoryLabel(id: string) {
  return t.labels.categories[id] ?? id;
}

export function NewsCard({ item, compact = false }: { item: FeedItem; compact?: boolean }) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  return (
    <article className={`news-card ${item.relevance.shown ? '' : 'news-card-hidden'}`}>
      <header className="news-head">
        <RelevanceBadge level={item.relevance.level} score={item.relevance.score} />
        <span className="badge badge-cat">{categoryLabel(item.category)}</span>
        <span className={`badge hr-${item.horizon_relevance}`}>{t.horizonRelevance[item.horizon_relevance]}</span>
        {item.is_synthetic && <SyntheticBadge />}
      </header>
      <h3 className="news-title">{item.title}</h3>
      <p className="news-meta">
        <span>{item.source}</span> · <time dateTime={item.published_at}>{formatDate(item.published_at)}</time>
        {item.tickers.length > 0 && (
          <>
            {' · '}
            {item.tickers.map((tk) => <span key={tk} className="ticker">{tk}</span>)}
          </>
        )}
      </p>
      {item.relevance.shown && !compact && <p className="news-summary">{item.explanation.summary}</p>}
      {!item.relevance.shown && (
        <p className="news-hidden-reason">
          <span aria-hidden="true">⦸ </span>
          {item.explanation.summary}
        </p>
      )}
      <div className="news-actions">
        <button type="button" className="btn btn-why" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((o) => !o)}>
          {open ? t.card.closeWhy : t.card.why}
        </button>
        <a className="btn btn-ghost" href={item.url} target="_blank" rel="noreferrer noopener">
          {t.card.openSource} <span aria-hidden="true">↗</span>
        </a>
      </div>
      {open && (
        <section id={panelId} className="why-panel" aria-label={t.card.why}>
          <div className="why-grid">
            <div>
              <h4>{t.card.rulesTitle}</h4>
              <RuleHits hits={item.relevance.rule_hits} />
              <p className="small">
                <Term id="concentration">{t.card.positionWeight}</Term> : <strong>{formatPct(item.relevance.position_weight)}</strong>
              </p>
            </div>
            <div>
              <h4>{t.card.claimsTitle}</h4>
              <ExplanationView explanation={item.explanation} />
            </div>
          </div>
          {item.historical_context && <HistoricalContextView ctx={item.historical_context} />}
        </section>
      )}
    </article>
  );
}
