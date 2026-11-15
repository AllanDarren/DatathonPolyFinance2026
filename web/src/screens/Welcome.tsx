import { api } from '../api/client';
import { ErrorBox, Skeleton } from '../components/Feedback';
import { useAsync } from '../lib/useAsync';
import { useApp } from '../state/store';
import { t } from '../strings';

export function Welcome() {
  const { choosePersona, go } = useApp();
  const personas = useAsync(() => api.getPersonas(), []);

  return (
    <div className="welcome">
      <section className="hero">
        <p className="eyebrow">{t.tagline}</p>
        <h1>{t.welcome.title}</h1>
        <p className="lead">{t.welcome.lead}</p>
        <p className="disclaimer-inline"><span aria-hidden="true">ⓘ</span> {t.disclaimer}</p>
      </section>
      <div className="choice-grid">
        <section className="panel choice">
          <h2>{t.welcome.personaTitle}</h2>
          <p className="muted">{t.welcome.personaHint}</p>
          {personas.loading && <Skeleton lines={3} label="Chargement des profils…" />}
          {personas.error ? <ErrorBox error={personas.error} onRetry={personas.reload} /> : null}
          <div className="persona-list">
            {personas.data?.map((p) => (
              <button key={p.id} type="button" className="persona-btn" onClick={() => choosePersona(p)}>
                <span className="persona-name">{t.welcome.loadPersona(p.profile.label)}</span>
                <span className="persona-desc">{p.label}</span>
              </button>
            ))}
          </div>
        </section>
        <section className="panel choice">
          <h2>{t.welcome.questionnaireTitle}</h2>
          <p className="muted">{t.welcome.questionnaireHint}</p>
          <button type="button" className="btn btn-primary" onClick={() => go('questionnaire')}>
            {t.welcome.startQuestionnaire}
          </button>
        </section>
      </div>
    </div>
  );
}
