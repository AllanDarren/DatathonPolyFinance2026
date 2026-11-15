// Tableau de bord découpé en onglets : une action principale par onglet.
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { EvidenceProvider } from '../components/Evidence';
import { ErrorBox, Skeleton } from '../components/Feedback';
import { formatDate } from '../lib/format';
import { hrefFor, useApp, type Step } from '../state/store';
import { t } from '../strings';
import { CalendarPage } from './CalendarPage';
import { Compare } from './Compare';
import { ConsiderPage } from './ConsiderPage';
import { FeedPage } from './FeedPage';
import { OverviewPage } from './OverviewPage';

const TABS: { step: Step; label: string; icon: string }[] = [
  { step: 'overview', label: t.tabs.overview, icon: '◔' },
  { step: 'feed', label: t.tabs.feed, icon: '☰' },
  { step: 'consider', label: t.tabs.consider, icon: '⚖' },
  { step: 'compare', label: t.tabs.compare, icon: '⇄' },
  { step: 'calendar', label: t.tabs.calendar, icon: '▦' },
];

export function DashboardShell({ tab }: { tab: Step }) {
  const { profile, portfolio, feed, setFeed, go } = useApp();
  const [error, setError] = useState<unknown>(null);
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!profile || !portfolio || feed) return;
    let alive = true;
    setError(null);
    api.buildFeed(profile, portfolio).then(
      (f) => alive && setFeed(f),
      (e: unknown) => alive && setError(e),
    );
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile, portfolio, feed, tick]);

  if (!profile || !portfolio) return null;

  return (
    <div className="dashboard">
      <header className="dash-head">
        <h1>{t.dashboard.title}</h1>
        {feed && <p className="muted small">{t.dashboard.asOf(formatDate(feed.data_as_of), formatDate(feed.news_as_of))}</p>}
      </header>
      <nav className="tabs" aria-label={t.tabs.label}>
        {TABS.map((x) => (
          <a
            key={x.step}
            href={hrefFor(x.step)}
            className={`tab ${tab === x.step ? 'tab-on' : ''}`}
            aria-current={tab === x.step ? 'page' : undefined}
            onClick={(e) => {
              e.preventDefault();
              go(x.step);
            }}
          >
            <span aria-hidden="true">{x.icon}</span> {x.label}
          </a>
        ))}
      </nav>
      {tab === 'compare' ? (
        <Compare />
      ) : tab === 'consider' ? (
        <ConsiderPage />
      ) : error && !feed ? (
        <ErrorBox error={error} onRetry={() => setTick((n) => n + 1)} />
      ) : !feed ? (
        <Skeleton lines={6} label={t.dashboard.loading} />
      ) : (
        <EvidenceProvider evidence={feed.evidence}>
          {tab === 'feed' && <FeedPage feed={feed} />}
          {tab === 'overview' && <OverviewPage feed={feed} />}
          {tab === 'calendar' && <CalendarPage feed={feed} />}
        </EvidenceProvider>
      )}
    </div>
  );
}
