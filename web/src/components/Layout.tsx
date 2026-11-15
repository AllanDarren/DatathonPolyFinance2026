// En-tête minimal : le logo (retour au tableau de bord) à gauche, le profil dans le coin droit.
// Le menu du profil offre « Mon profil » et « Déconnexion ». Les hypothèses et limites (exigées par
// la consigne : sources, hypothèses, facteurs clés et limites) restent accessibles depuis le pied de page.
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { useApp } from '../state/store';
import { t } from '../strings';
import { LimitsDrawer } from './LimitsDrawer';

function ProfileMenu() {
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
  return (
    <div className="profile-menu" ref={ref}>
      <button
        type="button"
        className="profile-chip"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${t.nav.profileMenu} : ${name}`}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="avatar" aria-hidden="true">{name.charAt(0).toUpperCase()}</span>
        <span className="profile-chip-label">{name}</span>
        <span aria-hidden="true" className="caret">▾</span>
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

export function Layout({ children }: { children: ReactNode }) {
  const { go, setLimitsOpen, profile, portfolio, step } = useApp();
  const ready = Boolean(profile && portfolio);
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
          <img src="/favicon.svg" alt="" width={28} height={28} />
          <span>{t.appName}</span>
        </button>
        {step !== 'welcome' && <ProfileMenu />}
      </header>
      <main id="main" className="main">{children}</main>
      <footer className="footer">
        <p>
          <span aria-hidden="true">ⓘ </span>{t.disclaimer} ·{' '}
          <button type="button" className="link-btn" onClick={() => setLimitsOpen(true)}>{t.nav.limits}</button>
        </p>
      </footer>
      <LimitsDrawer />
    </div>
  );
}
