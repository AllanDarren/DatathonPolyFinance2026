// Onglet « Mon portefeuille » : expositions et concentration, avec les limites du profil à côté.
import { PositionsQuality } from '../components/DataQuality';
import { PortfolioSummary } from '../components/PortfolioSummary';
import { useApp } from '../state/store';
import { t } from '../strings';
import type { FeedResponse } from '../types/contracts';

export function OverviewPage({ feed }: { feed: FeedResponse }) {
  const { go, portfolio } = useApp();
  const un = portfolio?.unanalyzed;
  return (
    <div className="overview">
      <PortfolioSummary summary={feed.portfolio_summary} limits={feed.profile.limits} />
      {un && un.tickers.length > 0 && (
        <p className="callout callout-warn small">{t.portfolio.unanalyzed(`${Math.round(un.weight * 100)} %`, un.tickers.join(', '))}</p>
      )}
      {feed.data_quality && feed.data_quality.length > 0 && <PositionsQuality reports={feed.data_quality} />}
      <section className="panel cta-panel">
        <h2 className="h-panel">{t.overview.nextTitle}</h2>
        <p className="muted">{t.overview.nextLead}</p>
        <div className="row-start">
          <button type="button" className="btn btn-primary" onClick={() => go('consider')}>{t.overview.toConsider}</button>
          <button type="button" className="btn btn-secondary" onClick={() => go('feed')}>{t.overview.toFeed}</button>
        </div>
      </section>
    </div>
  );
}
