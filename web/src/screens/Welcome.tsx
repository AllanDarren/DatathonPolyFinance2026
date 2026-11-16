// Accueil : promesse en une phrase, démonstration du tri (titres fictifs, étiquetés), profils d'exemple.
import { useRef } from 'react';
import { api } from '../api/client';
import { ErrorBox, Skeleton, SyntheticBadge } from '../components/Feedback';
import { useAsync } from '../lib/useAsync';
import { useApp } from '../state/store';
import { t } from '../strings';
import type { Persona, Profile } from '../types/contracts';

/** Démonstration statique du tri : titres fictifs, jamais présentés comme réels. */
const DEMO: { title: string; kept: boolean; tag: string; reason: string }[] = [
  { title: '« Le marché va-t-il s’effondrer ? » — chronique du jour', kept: false, tag: '', reason: 'opinion · aucun fait nouveau' },
  { title: 'Washington restreint de nouvelles ventes de puces Nvidia', kept: true, tag: 'NVDA · 20 % de ton portefeuille', reason: 'ta plus grosse position est directement touchée' },
  { title: 'Top 10 des titres à surveiller avant Noël', kept: false, tag: '', reason: 'liste promotionnelle' },
  { title: 'Le bitcoin recule de 2 % en séance', kept: false, tag: '', reason: 'bruit court terme · horizon 20 ans' },
  { title: 'Microsoft annonce une émission d’obligations', kept: true, tag: 'MSFT · source primaire', reason: 'change la structure financière d’un titre à 15 %' },
  { title: 'Même dépêche reprise par 4 autres médias', kept: false, tag: '', reason: 'doublon regroupé' },
];

/** Position visuelle de la tolérance au risque (jauge décorative, le libellé porte l'information). */
const RISK_GAUGE: Record<Profile['risk_tolerance'], number> = { low: 0.18, low_moderate: 0.32, moderate: 0.52, high: 0.85 };
const PERSONA_TONE: Record<string, string> = { robert: 'tone-blue', amira: 'tone-lime', mateo: 'tone-orange' };

export function personaName(p: Profile): string {
  return p.label.split(/[—–-]/)[0]!.trim();
}

function personaBlurb(p: Persona): string {
  const parts = p.label.split(/[—–]/);
  const s = (parts[1] ?? t.labels.objective[p.profile.objective] ?? '').trim();
  return s.charAt(0).toUpperCase() + s.slice(1);
}

function PersonaCard({ p, onPick }: { p: Persona; onPick: () => void }) {
  const name = personaName(p.profile);
  const tone = PERSONA_TONE[p.id] ?? 'tone-lime';
  const risk = t.labels.risk[p.profile.risk_tolerance] ?? p.profile.risk_tolerance;
  return (
    <button type="button" className={`persona-card ${tone}`} onClick={onPick}>
      <span className="pc-top">
        <span className="pc-avatar" aria-hidden="true">{name.charAt(0)}</span>
        <span className="chip-mono">{t.welcome.horizonChip(p.profile.horizon_years)}</span>
      </span>
      <span className="pc-name">{name}</span>
      <span className="pc-blurb">{personaBlurb(p)}</span>
      <span className="pc-risk mono">
        <span>{t.welcome.riskLabel}</span>
        <span>{risk.toLowerCase()}</span>
      </span>
      <span className="pc-gauge" aria-hidden="true">
        <span style={{ width: `${RISK_GAUGE[p.profile.risk_tolerance] * 100}%` }} />
      </span>
      <span className="pc-cta">{t.welcome.loadPersona(name)} <span aria-hidden="true">→</span></span>
    </button>
  );
}

export function Welcome() {
  const { choosePersona, go } = useApp();
  const personas = useAsync(() => api.getPersonas(), []);
  const personasRef = useRef<HTMLElement>(null);

  return (
    <div className="home">
      <section className="home-hero">
        <div className="home-copy">
          <p className="kicker mono">{t.welcome.kicker}</p>
          <h1 className="display">
            {t.welcome.heroA}
            <br />
            {t.welcome.heroB}
            <span className="accent">{t.welcome.heroSignal}</span>
          </h1>
          <p className="home-lead">{t.welcome.heroLead}</p>
          <div className="home-ctas">
            <button type="button" className="btn btn-primary btn-lg" onClick={() => go('questionnaire')}>
              {t.welcome.findProfile} <span aria-hidden="true">→</span>
            </button>
            <button
              type="button"
              className="btn btn-outline btn-lg"
              onClick={() => personasRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
            >
              {t.welcome.tryExample}
            </button>
          </div>
          <p className="mono muted small">{t.disclaimer}</p>
        </div>

        <figure className="demo-feed" aria-label={t.welcome.demoTag}>
          <div className="demo-head mono">
            <span>{t.welcome.demoHead('amira', 20)}</span>
            <SyntheticBadge />
          </div>
          <ul>
            {DEMO.map((d) =>
              d.kept ? (
                <li key={d.title} className="demo-kept">
                  <p className="mono demo-tag"><span className="pill-lime">{t.welcome.demoKept}</span> {d.tag}</p>
                  <p className="demo-title">{d.title}</p>
                  <p className="mono demo-why"><span aria-hidden="true">→ </span>{d.reason}</p>
                </li>
              ) : (
                <li key={d.title} className="demo-dropped">
                  <s>{d.title}</s>
                  <span className="mono">{d.reason}</span>
                </li>
              ),
            )}
          </ul>
          <figcaption className="small muted">{t.welcome.demoCaption}</figcaption>
        </figure>
      </section>

      <section aria-labelledby="sources-title">
        <div className="stat-row">
          {t.welcome.stats.map((s) => (
            <div key={s.label} className="stat-cell">
              <span className={`stat-big mono ${s.accent ? 'accent' : ''}`}>{s.value}</span>
              <span className="stat-txt">{s.label}</span>
            </div>
          ))}
        </div>
        <p className="mono muted small stat-asof">{t.welcome.statsAsOf}</p>
        <h2 id="sources-title" className="sr-only">{t.welcome.sourcesTitle}</h2>
        <dl className="source-list">
          {t.welcome.sources.map((s) => (
            <div key={s.k}>
              <dt className="mono">{s.k}</dt>
              <dd>{s.v}</dd>
            </div>
          ))}
        </dl>
      </section>

      <section className="home-personas" ref={personasRef} aria-labelledby="personas-title">
        <div className="section-head">
          <h2 id="personas-title" className="h-section">{t.welcome.personasTitle}</h2>
          <p className="muted">{t.welcome.personasLead}</p>
        </div>
        {personas.loading && <Skeleton lines={3} label="Chargement des profils…" />}
        {personas.error ? <ErrorBox error={personas.error} onRetry={personas.reload} /> : null}
        <div className="persona-grid">
          {personas.data?.map((p) => <PersonaCard key={p.id} p={p} onPick={() => choosePersona(p)} />)}
        </div>
      </section>
    </div>
  );
}
