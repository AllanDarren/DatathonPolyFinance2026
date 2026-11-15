import type { ReactNode } from 'react';
import { IS_MOCK } from '../api/config';
import { DASHBOARD_TABS, useApp } from '../state/store';
import { t } from '../strings';
import { LimitsDrawer } from './LimitsDrawer';

export function Layout({ children }: { children: ReactNode }) {
  const { step, go, reset, setLimitsOpen, profile, portfolio } = useApp();
  const ready = Boolean(profile && portfolio);
  return (
    <div className="app">
      <a href="#main" className="skip-link">Aller au contenu</a>
      <div className="disclaimer-bar" role="note">
        <span aria-hidden="true">ⓘ</span> {t.disclaimer}
        {IS_MOCK && <span className="mock-flag">{t.mockBanner}</span>}
      </div>
      <header className="topbar">
        <button type="button" className="brand" onClick={reset} aria-label={`${t.appName} — ${t.nav.restart}`}>
          <img src="/favicon.svg" alt="" width={28} height={28} />
          <span>{t.appName}</span>
        </button>
        <nav className="topnav" aria-label="Navigation principale">
          {profile && <span className="who">{profile.label}</span>}
          {ready && !DASHBOARD_TABS.includes(step) && (
            <button type="button" className="btn btn-ghost" onClick={() => go('feed')}>{t.nav.dashboard}</button>
          )}
          {profile && step !== 'profile' && (
            <button type="button" className="btn btn-ghost" onClick={() => go('profile')}>{t.nav.profile}</button>
          )}
          <button type="button" className="btn btn-ghost" onClick={() => setLimitsOpen(true)}>{t.nav.limits}</button>
          {step !== 'welcome' && (
            <button type="button" className="btn btn-ghost" onClick={reset}>{t.nav.restart}</button>
          )}
        </nav>
      </header>
      <main id="main" className="main">{children}</main>
      <footer className="footer">
        <p>{t.tagline} · {t.disclaimer}</p>
      </footer>
      <LimitsDrawer />
    </div>
  );
}
