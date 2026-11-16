import { useEffect, useRef } from 'react';
import { useApp } from '../state/store';
import { t } from '../strings';

export function LimitsDrawer() {
  const { limitsOpen, setLimitsOpen, feed } = useApp();
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    if (!limitsOpen) return;
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && setLimitsOpen(false);
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [limitsOpen, setLimitsOpen]);
  if (!limitsOpen) return null;

  return (
    <div className="drawer-backdrop" onClick={() => setLimitsOpen(false)}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="limits-title" onClick={(e) => e.stopPropagation()}>
        <header className="drawer-head">
          <h2 id="limits-title">{t.limits.title}</h2>
          <button ref={closeRef} type="button" className="btn btn-ghost" onClick={() => setLimitsOpen(false)}>{t.limits.close}</button>
        </header>
        {!feed ? (
          <p className="muted">{t.limits.empty}</p>
        ) : (
          <>
            <h3 className="h-small">{t.limits.limits}</h3>
            <ul>{feed.limits.map((d, i) => <li key={i}>{d}</li>)}</ul>
          </>
        )}
      </aside>
    </div>
  );
}
