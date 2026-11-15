// Preuves cliquables : chaque chiffre renvoie à un objet Evidence de la réponse.
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import type { Evidence } from '../types/contracts';
import { formatDate, formatEvidenceValue } from '../lib/format';
import { t } from '../strings';

type Ctx = { evidence: Record<string, Evidence>; open: (id: string) => void };
const EvidenceCtx = createContext<Ctx>({ evidence: {}, open: () => {} });

export function EvidenceProvider({ evidence, children }: { evidence: Record<string, Evidence>; children: ReactNode }) {
  const [openId, setOpenId] = useState<string | null>(null);
  return (
    <EvidenceCtx.Provider value={{ evidence, open: setOpenId }}>
      {children}
      {openId && <EvidenceDrawer id={openId} evidence={evidence[openId]} onClose={() => setOpenId(null)} />}
    </EvidenceCtx.Provider>
  );
}

export function EvidenceChip({ id }: { id: string }) {
  const { evidence, open } = useContext(EvidenceCtx);
  const ev = evidence[id];
  return (
    <button type="button" className="evidence-chip" onClick={() => open(id)} aria-label={`Voir la preuve ${id}`}>
      {id}
      {ev && <span className="evidence-chip-kind">{ev.kind.replace('_', ' ')}</span>}
    </button>
  );
}

function EvidenceDrawer({ id, evidence, onClose }: { id: string; evidence?: Evidence; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose();
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [onClose]);

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-labelledby="ev-title" onClick={(e) => e.stopPropagation()}>
        <header className="drawer-head">
          <h2 id="ev-title">{t.evidence.title} {id}</h2>
          <button ref={closeRef} type="button" className="btn btn-ghost" onClick={onClose}>{t.evidence.close}</button>
        </header>
        {!evidence ? (
          <p>{t.evidence.missing}</p>
        ) : (
          <>
            <p className="ev-statement">{evidence.statement}</p>
            <dl className="ev-list">
              <dt>{t.evidence.value}</dt>
              <dd className="ev-value">{formatEvidenceValue(evidence.value, evidence.unit)}</dd>
              <dt>{t.evidence.asOf}</dt>
              <dd>{formatDate(evidence.as_of)}</dd>
              <dt>{t.evidence.source}</dt>
              <dd>
                {/^https?:\/\//.test(evidence.source) ? (
                  <a href={evidence.source} target="_blank" rel="noreferrer noopener">{evidence.source}</a>
                ) : (
                  <code>{evidence.source}</code>
                )}
              </dd>
              <dt>{t.evidence.computedBy}</dt>
              <dd><code>{evidence.computed_by}</code></dd>
              <dt>{t.evidence.inputs}</dt>
              <dd><pre className="ev-inputs">{JSON.stringify(evidence.inputs, null, 2)}</pre></dd>
            </dl>
          </>
        )}
      </aside>
    </div>
  );
}
