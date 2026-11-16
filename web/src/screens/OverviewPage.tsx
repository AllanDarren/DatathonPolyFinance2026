// « Mon portefeuille » : répartition, deux jauges face aux limites du profil, ce qu'il y a à lire,
// puis les positions avec leur poids et l'état de leurs données. Aucun calcul financier ici : on affiche
// les poids et les parts envoyés par l'API, et on compte des nouvelles.
import { EvidenceChip } from '../components/Evidence';
import { Term } from '../components/Term';
import { formatCad, formatDate, formatPct } from '../lib/format';
import { useApp } from '../state/store';
import { t } from '../strings';
import type { FeedResponse, QualityReport } from '../types/contracts';

export const CLASS_TONE: Record<string, string> = {
  equity_us: 'var(--c1)',
  crypto: 'var(--c2)',
  equity_etf: 'var(--c3)',
  bond_etf: 'var(--c4)',
  equity_ca: 'var(--c5)',
  gold_etf: 'var(--c6)',
};

function ClassBar({ weights }: { weights: Record<string, number> }) {
  const rows = Object.entries(weights).filter(([, w]) => w > 0).sort((a, b) => b[1] - a[1]);
  return (
    <section className="card" aria-labelledby="cls-title">
      <h2 id="cls-title" className="card-title">{t.overviewPage.byClass}</h2>
      <div className="stack-bar" aria-hidden="true">
        {rows.map(([k, w]) => <span key={k} style={{ flexGrow: w, background: CLASS_TONE[k] ?? 'var(--muted)' }} />)}
      </div>
      <ul className="stack-legend">
        {rows.map(([k, w]) => (
          <li key={k}>
            <span className="swatch" style={{ background: CLASS_TONE[k] ?? 'var(--muted)' }} aria-hidden="true" />
            {t.labels.assetClass[k] ?? k} <span className="mono muted">{formatPct(w, 0)}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function HighVolCard({ share, limit }: { share: number; limit: number }) {
  const over = share > limit;
  return (
    <section className={`card kpi-card ${over ? 'is-over' : ''}`}>
      <h2 className="card-title"><Term id="volatility">{t.overviewPage.highVol}</Term></h2>
      <p className="kpi-big mono">{formatPct(share, 0)}</p>
      <div className="gauge" aria-hidden="true">
        <span className="gauge-fill" style={{ width: `${Math.min(share, 1) * 100}%` }} />
        <span className="gauge-mark" style={{ left: `${Math.min(limit, 1) * 100}%` }} />
      </div>
      <p className="small muted">
        {t.overviewPage.highVolLimit(formatPct(limit, 0))} —{' '}
        <strong className={over ? 'txt-warn' : 'txt-ok'}>
          <span aria-hidden="true">{over ? '⚠ ' : '✓ '}</span>
          {over ? t.overviewPage.highVolOver : t.overviewPage.highVolOk}
        </strong>
      </p>
    </section>
  );
}

function ConcentrationCard({ summary }: { summary: FeedResponse['portfolio_summary'] }) {
  const top = summary.top_positions.slice(0, 3);
  return (
    <section className="card kpi-card">
      <h2 className="card-title"><Term id="concentration">{t.overviewPage.concentration}</Term></h2>
      <p className="kpi-big mono">{formatPct(summary.top3_concentration, 0)}</p>
      <div className="seg-bar" aria-hidden="true">
        {top.map((p, i) => <span key={p.ticker} className={`seg seg-${i}`} style={{ width: `${p.weight * 100}%` }} />)}
      </div>
      <p className="small muted">{t.overviewPage.concentrationText(top.map((p) => p.ticker).join(', '))}</p>
    </section>
  );
}

function ReadNowCard({ feed }: { feed: FeedResponse }) {
  const { go } = useApp();
  const kept = feed.items.filter((i) => i.relevance.shown);
  const total = kept.length + feed.hidden.count;
  const counts = new Map<string, number>();
  kept.forEach((i) => i.tickers.forEach((tk) => counts.set(tk, (counts.get(tk) ?? 0) + 1)));
  const [topTicker, topN] = [...counts.entries()].sort((a, b) => b[1] - a[1])[0] ?? [null, 0];
  return (
    <section className="card card-lime">
      <h2 className="card-title">{t.overviewPage.readNow}</h2>
      <p className="kpi-big mono">{kept.length}</p>
      <p className="small">{t.overviewPage.readNowText(total, topTicker, topN)}</p>
      <a
        href="#/fil"
        className="lime-link"
        onClick={(e) => {
          e.preventDefault();
          go('feed');
        }}
      >
        {t.overviewPage.openFeed}
      </a>
    </section>
  );
}

const Q_ICON = { ok: '✓', warning: '⚠', blocking: '✖' } as const;

function QualityCell({ q }: { q: QualityReport | undefined }) {
  if (!q) return <span className="muted">—</span>;
  const msg = q.status === 'ok' ? t.overviewPage.dataOk : (q.warnings_fr[0] ?? t.quality.status[q.status]);
  return (
    <span className={`q-cell q-txt-${q.status}`} title={[...q.warnings_fr, ...q.notes_fr].join(' ') || undefined}>
      <span aria-hidden="true">{Q_ICON[q.status]} </span>
      {msg}
      <EvidenceChip id={q.evidence_id} />
    </span>
  );
}

function PositionsTable({ feed }: { feed: FeedResponse }) {
  const { portfolio } = useApp();
  if (!portfolio) return null;
  const positions = [...portfolio.positions].filter((p) => p.in_universe).sort((a, b) => b.amount - a.amount);
  // Échelle d'affichage seulement : un peu de marge pour que le repère de limite reste dans la piste.
  const maxW = Math.max(...positions.map((p) => p.weight), feed.profile.limits.max_single_position, 0.01) * 1.15;
  const limit = feed.profile.limits.max_single_position;
  const quality = new Map((feed.data_quality ?? []).map((q) => [q.ticker, q]));
  return (
    <section className="card card-flush" aria-label="Positions">
      <table className="pos-table">
        <thead>
          <tr>
            <th scope="col">{t.overviewPage.colTicker}</th>
            <th scope="col">{t.overviewPage.colClass}</th>
            <th scope="col" className="num">{t.overviewPage.colAmount}</th>
            <th scope="col">
              {t.overviewPage.colWeight}{' '}
              <span className="muted small">(<span className="legend-mark" aria-hidden="true" /> {t.overviewPage.limitMarker} {formatPct(limit, 0)})</span>
            </th>
            <th scope="col" className="right">{t.overviewPage.colData}</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => {
            const over = p.weight > limit;
            return (
              <tr key={p.ticker}>
                <th scope="row" className="mono strong">{p.ticker}</th>
                <td>{t.labels.assetClass[p.asset_class] ?? p.asset_class}</td>
                <td className="num mono">{formatCad(p.amount)}</td>
                <td>
                  <span className="wbar">
                    <span className="wbar-track" aria-hidden="true">
                      <span className={`wbar-fill ${over ? 'is-over' : ''}`} style={{ width: `${(p.weight / maxW) * 100}%` }} />
                      <span className="wbar-mark" style={{ left: `${(limit / maxW) * 100}%` }} />
                    </span>
                    <span className="mono small">
                      {formatPct(p.weight, 0)}
                      {over && <span className="txt-warn" title={t.overviewPage.overLimit}> ⚠<span className="sr-only"> {t.overviewPage.overLimit}</span></span>}
                    </span>
                  </span>
                </td>
                <td className="right small"><QualityCell q={quality.get(p.ticker)} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </section>
  );
}

export function OverviewPage({ feed }: { feed: FeedResponse }) {
  const { portfolio } = useApp();
  const un = portfolio?.unanalyzed;
  return (
    <div className="overview">
      <header className="page-head page-head-row">
        <div>
          <p className="mono muted small">{t.shell.asOf(formatDate(feed.data_as_of), formatDate(feed.news_as_of))}</p>
          <h1 className="page-title">{t.overviewPage.title}</h1>
        </div>
        {portfolio && (
          <p className="total mono">
            {formatCad(portfolio.total_amount).replace(/\s?\$/, '')} <span>$</span> <small>CAD</small>
          </p>
        )}
      </header>

      <ClassBar weights={feed.portfolio_summary.asset_class_weights} />
      <div className="kpi-grid">
        <HighVolCard share={feed.portfolio_summary.high_vol_share} limit={feed.profile.limits.max_high_vol_share} />
        <ConcentrationCard summary={feed.portfolio_summary} />
        <ReadNowCard feed={feed} />
      </div>
      {un && un.tickers.length > 0 && (
        <p className="callout callout-warn small">{t.portfolio.unanalyzed(`${Math.round(un.weight * 100)} %`, un.tickers.join(', '))}</p>
      )}
      <PositionsTable feed={feed} />
    </div>
  );
}
