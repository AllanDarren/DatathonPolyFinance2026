// Tableau de bord : la navigation est dans la barre latérale (Layout), une action principale par section.
import { useEffect, useState } from 'react';
import { api } from '../api/client';
import { EvidenceProvider } from '../components/Evidence';
import { ErrorBox, Skeleton } from '../components/Feedback';
import { formatDate } from '../lib/format';
import { useApp, type Step } from '../state/store';
import { t } from '../strings';
import { CalendarPage } from './CalendarPage';
import { Compare } from './Compare';
import { ConsiderPage } from './ConsiderPage';
import { FeedPage } from './FeedPage';
import { OverviewPage } from './OverviewPage';

const TITLES: Partial<Record<Step, string>> = {
  feed: t.tabs.feed,
  consider: t.tabs.consider,
  compare: t.tabs.compare,
  calendar: t.tabs.calendar,
};

export function DashboardShell({ tab }: { tab: Step }) {
  const { profile, portfolio, feed, setFeed } = useApp();
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
  const title = TITLES[tab];

  return (
    <div className="dashboard">
      {title && (
        <header className="page-head">
          {feed && <p className="mono muted small">{t.shell.asOf(formatDate(feed.data_as_of), formatDate(feed.news_as_of))}</p>}
          <h1 className="page-title">{title}</h1>
        </header>
      )}
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
