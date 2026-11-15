// Navigation identique sur tous les écrans : marque à gauche, liens au centre, profil dans le coin.
// L'avertissement « simulation, pas un conseil » reste dans le pied de page (et sur l'accueil).
import type { ReactNode } from 'react';
import { DASHBOARD_TABS, useApp } from '../state/store';
import { t } from '../strings';
import { LimitsDrawer } from './LimitsDrawer';

export function Layout({ children }: { children: ReactNode }) {
  const { step, go, reset, setLimitsOpen, profile, portfolio } = useApp();
  const ready = Boolean(profile && portfolio);
  const onDashboard = DASHBOARD_TABS.includes(step);
  return (
    <div className="app">
      <a href="#main" className="skip-link">Aller au contenu</a>
      <header className="topbar">
        <button type="button" className="brand" onClick={reset} aria-label={`${t.appName} — ${t.nav.restart}`}>
          <img src="/favicon.svg" alt="" width={28} height={28} />
          <span>{t.appName}</span>
        </button>
        <nav className="topnav" aria-label="Navigation principale">
          <button
            type="button"
            className={`btn btn-ghost ${onDashboard ? 'nav-on' : ''}`}
            aria-current={onDashboard ? 'page' : undefined}
            disabled={!ready}
            title={ready ? undefined : t.nav.dashboardLocked}
            onClick={() => go('feed')}
          >
            {t.nav.dashboard}
          </button>
          <button type="button" className="btn btn-ghost" onClick={() => setLimitsOpen(true)}>{t.nav.limits}</button>
          {step !== 'welcome' && (
            <button type="button" className="btn btn-ghost" onClick={reset}>{t.nav.restart}</button>
          )}
        </nav>
        <div className="profile-corner">
          {profile ? (
            <button
              type="button"
              className={`profile-chip ${step === 'profile' ? 'nav-on' : ''}`}
              onClick={() => go('profile')}
              aria-label={`${t.nav.profile} : ${profile.label}`}
            >
              <span className="avatar" aria-hidden="true">{profile.label.trim().charAt(0).toUpperCase()}</span>
              <span className="profile-chip-label">{profile.label.split(/[—–-]/)[0]!.trim()}</span>
            </button>
          ) : (
            <span className="muted small">{t.nav.noProfile}</span>
          )}
        </div>
      </header>
      <main id="main" className="main">{children}</main>
      <footer className="footer">
        <p><span aria-hidden="true">ⓘ </span>{t.disclaimer} · {t.tagline}</p>
      </footer>
      <LimitsDrawer />
    </div>
  );
}
