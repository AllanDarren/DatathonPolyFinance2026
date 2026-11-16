// Claims (Fait / Hypothèse / Scénario), règles déclenchées et statut du gardien.
// Le texte d'un claim est déjà rendu par le serveur : on l'affiche comme texte, jamais comme HTML.
import type { Claim, ClaimLabel, Explanation, RuleHit } from '../types/contracts';
import { formatPct } from '../lib/format';
import { t } from '../strings';
import { EvidenceChip } from './Evidence';

const LABEL_ICON: Record<ClaimLabel, string> = { fact: '■', hypothesis: '?', scenario: '◇' };

export function ClaimLabelBadge({ label }: { label: ClaimLabel }) {
  return (
    <span className={`claim-label claim-${label}`}>
      <span aria-hidden="true">{LABEL_ICON[label]}</span> {t.claimLabels[label]}
    </span>
  );
}

export function ClaimList({ claims }: { claims: Claim[] }) {
  return (
    <ul className="claims">
      {claims.map((c, i) => (
        <li key={i} className={c.verified === 'unsupported' ? 'claim claim-unsupported' : 'claim'}>
          <ClaimLabelBadge label={c.label} />
          <span className="claim-text">
            {c.verified === 'unsupported' && (
              <span className="warn" title={t.card.unsupported}>
                <span aria-hidden="true">⚠ </span>
                <span className="sr-only">{t.card.unsupported} : </span>
              </span>
            )}
            {c.text}
          </span>
          {c.evidence_ids.length > 0 && (
            <span className="claim-evidence">
              {c.evidence_ids.map((id) => <EvidenceChip key={id} id={id} />)}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

export function RuleHits({ hits }: { hits: RuleHit[] }) {
  if (hits.length === 0) return null;
  return (
    <ul className="rule-hits">
      {hits.map((h) => (
        <li key={h.rule_id} className={`rule-hit sev-${h.severity ?? 'none'}`}>
          <span className="rule-text">{h.text}</span>
          {h.observed !== undefined && h.limit !== undefined && (
            <span className="rule-obs">{t.consider.observedVsLimit(formatPct(h.observed, 0), formatPct(h.limit, 0))}</span>
          )}
          <code className="rule-id">{h.rule_id}</code>
        </li>
      ))}
    </ul>
  );
}

export function GuardianStatus({ guardian }: { guardian: Explanation['guardian'] }) {
  const map = {
    passed: { icon: '✔', text: t.card.guardianPassed, cls: 'ok' },
    flagged: { icon: '⚠', text: t.card.guardianFlagged, cls: 'warn' },
    not_run: { icon: '○', text: t.card.guardianNotRun, cls: 'muted' },
  } as const;
  const s = map[guardian.status];
  return (
    <div className={`guardian guardian-${s.cls}`}>
      <span aria-hidden="true">{s.icon}</span> {s.text}
      {guardian.flags.length > 0 && (
        <ul className="guardian-flags">
          {guardian.flags.map((f, i) => <li key={i}>{f}</li>)}
        </ul>
      )}
    </div>
  );
}

export function ExplanationView({ explanation }: { explanation: Explanation }) {
  return (
    <div className="explanation">
      {explanation.summary && <p className="expl-summary">{explanation.summary}</p>}
      <ClaimList claims={explanation.claims} />
      <div className="expl-foot">
        <GuardianStatus guardian={explanation.guardian} />
        <span className="muted small">{t.card.generatedBy[explanation.generated_by]}</span>
      </div>
    </div>
  );
}
