// Deux gabarits : un en-tête minimal (accueil, questionnaire, profil, import) et, une fois le profil et le
// portefeuille connus, une barre latérale (sections du tableau de bord + profil en bas, avec son menu).
// Les hypothèses et limites restent accessibles partout depuis le pied de page.
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { DASHBOARD_TABS, hrefFor, useApp, type Step } from '../state/store';
import { t } from '../strings';
import { LimitsDrawer } from './LimitsDrawer';

function Logo() {
  return (
    <span className="logo" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="18" height="18"><path d="M6 8h12M8 12h8M10 16h4" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" /></svg>
    </span>
  );
}

/** Icônes de navigation dessinées au trait (même épaisseur partout). */
const ICONS: Record<string, ReactNode> = {
  overview: <path d="M12 3a9 9 0 1 0 9 9h-9z M14 3.3A9 9 0 0 1 20.7 10H14z" />,
  feed: <path d="M4 7h16M4 12h11M4 17h7" />,
  consider: <path d="M12 4v16M6 8h12M6 8l-3 6h6zM18 8l-3 6h6z" />,
  compare: <path d="M4 9h14l-3-3M20 15H6l3 3" />,
  calendar: <path d="M4 7h16v13H4zM4 11h16M8 4v4M16 4v4" />,
};

const NAV: { step: Step; label: string }[] = [
  { step: 'overview', label: t.tabs.overview },
  { step: 'feed', label: t.tabs.feed },
  { step: 'consider', label: t.tabs.consider },
  { step: 'compare', label: t.tabs.compare },
  { step: 'calendar', label: t.tabs.calendar },
];

function ProfileMenu({ variant }: { variant: 'chip' | 'card' }) {
  const { profile, go, reset } = useApp();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setOpen(false);
    document.addEventListener('mousedown', onDoc);
    window.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDoc);
      window.removeEventListener('keydown', onKey);
    };
  }, [open]);

  if (!profile) return null;
  const name = profile.label.split(/[—–-]/)[0]!.trim();
  const risk = t.labels.risk[profile.risk_tolerance] ?? profile.risk_tolerance;
  return (
    <div className={`profile-menu profile-menu-${variant}`} ref={ref}>
      <button
        type="button"
        className={variant === 'card' ? 'profile-card' : 'profile-chip'}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${t.nav.profileMenu} : ${name}`}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="avatar" aria-hidden="true">{name.charAt(0).toUpperCase()}</span>
        <span className="profile-txt">
          <span className="profile-chip-label">{name}</span>
          {variant === 'card' && <span className="profile-sub">{t.shell.profileSub(profile.horizon_years, risk)}</span>}
        </span>
        <span aria-hidden="true" className="caret">{variant === 'card' ? '⋯' : '▾'}</span>
      </button>
      {open && (
        <ul className="menu" role="menu">
          <li role="none">
            <button type="button" role="menuitem" onClick={() => { setOpen(false); go('profile'); }}>
              {t.nav.profile}
            </button>
          </li>
          <li role="none">
            <button type="button" role="menuitem" onClick={() => { setOpen(false); reset(); }}>
              {t.nav.logout}
            </button>
          </li>
        </ul>
      )}
    </div>
  );
}

function Sidebar() {
  const { step, go, feed } = useApp();
  const kept = feed ? feed.items.filter((i) => i.relevance.shown).length : null;
  return (
    <aside className="sidebar">
      <button type="button" className="brand" onClick={() => go('overview')} aria-label={`${t.appName} — ${t.nav.dashboard}`}>
        <Logo />
        <span>AlphaForge</span>
      </button>
      <nav aria-label={t.shell.nav}>
        <ul className="side-nav">
          {NAV.map((x) => (
            <li key={x.step}>
              <a
                href={hrefFor(x.step)}
                className={`side-link ${step === x.step ? 'side-on' : ''}`}
                aria-current={step === x.step ? 'page' : undefined}
                onClick={(e) => {
                  e.preventDefault();
                  go(x.step);
                }}
              >
                <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" className="side-ico">{ICONS[x.step]}</svg>
                <span>{x.label}</span>
                {x.step === 'feed' && kept !== null && (
                  <span className="side-count" aria-label={t.shell.feedCount(kept)}>{kept}</span>
                )}
              </a>
            </li>
          ))}
        </ul>
      </nav>
      <div className="side-foot">
        <ProfileMenu variant="card" />
      </div>
    </aside>
  );
}

function Footer() {
  const { setLimitsOpen } = useApp();
  return (
    <footer className="footer">
      <span className="mono">{t.disclaimer}</span>
      <button type="button" className="link-btn mono" onClick={() => setLimitsOpen(true)}>{t.nav.limits}</button>
    </footer>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { go, profile, portfolio, step } = useApp();
  const ready = Boolean(profile && portfolio);
  const inDashboard = ready && DASHBOARD_TABS.includes(step);

  if (inDashboard) {
    return (
      <div className="shell">
        <a href="#main" className="skip-link">Aller au contenu</a>
        <Sidebar />
        <div className="shell-main">
          <main id="main" className="main">{children}</main>
          <Footer />
        </div>
        <LimitsDrawer />
      </div>
    );
  }

  return (
    <div className="app">
      <a href="#main" className="skip-link">Aller au contenu</a>
      <header className="topbar">
        <button
          type="button"
          className="brand"
          onClick={() => go(ready ? 'overview' : profile ? 'portfolio' : 'welcome')}
          aria-label={ready ? `${t.appName} — ${t.nav.dashboard}` : t.appName}
        >
          <Logo />
          <span>AlphaForge</span>
        </button>
        {step === 'welcome' ? (
          <button type="button" className="btn btn-light" onClick={() => go('questionnaire')}>{t.welcome.start}</button>
        ) : (
          <ProfileMenu variant="chip" />
        )}
      </header>
      <main id="main" className={`main ${step === 'welcome' ? 'main-wide' : ''}`}>{children}</main>
      <Footer />
      <LimitsDrawer />
    </div>
  );
}
