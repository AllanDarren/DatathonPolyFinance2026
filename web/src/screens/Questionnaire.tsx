// Questionnaire piloté par les données (GET /questionnaire) : aucune question codée en dur.
import { useState } from 'react';
import { api } from '../api/client';
import { ErrorBox, Skeleton } from '../components/Feedback';
import { useAsync } from '../lib/useAsync';
import { useApp } from '../state/store';
import { t } from '../strings';

export function Questionnaire() {
  const { setProfile, go } = useApp();
  const q = useAsync(() => api.getQuestionnaire(), []);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);

  if (q.loading) return <Skeleton lines={4} label="Chargement du questionnaire…" />;
  if (q.error || !q.data) return <ErrorBox error={q.error} onRetry={q.reload} />;

  const questions = q.data.questions;
  const question = questions[index];
  if (!question) return null;
  const isLast = index === questions.length - 1;
  const answered = Boolean(answers[question.id]);

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      setProfile(await api.scoreProfile(answers));
      go('profile');
    } catch (e) {
      setError(e);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel narrow questionnaire" aria-labelledby="q-title">
      <p className="eyebrow">{t.questionnaire.title} · {t.questionnaire.progress(index + 1, questions.length)}</p>
      <div className="progress" aria-hidden="true">
        <div className="progress-fill" style={{ width: `${((index + 1) / questions.length) * 100}%` }} />
      </div>
      <fieldset>
        <legend id="q-title" className="q-text">{question.text}</legend>
        {question.help && <p className="muted">{question.help}</p>}
        <div className="options">
          {question.options.map((o) => (
            <label key={o.id} className={`option ${answers[question.id] === o.id ? 'option-on' : ''}`}>
              <input
                type="radio"
                name={question.id}
                value={o.id}
                checked={answers[question.id] === o.id}
                onChange={() => setAnswers((a) => ({ ...a, [question.id]: o.id }))}
              />
              {o.label}
            </label>
          ))}
        </div>
      </fieldset>
      {error ? <ErrorBox error={error} /> : null}
      <div className="row-between">
        <button type="button" className="btn btn-secondary" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
          {t.questionnaire.previous}
        </button>
        {isLast ? (
          <button type="button" className="btn btn-primary" disabled={!answered || submitting} onClick={submit}>
            {t.questionnaire.finish}
          </button>
        ) : (
          <button type="button" className="btn btn-primary" disabled={!answered} onClick={() => setIndex((i) => i + 1)}>
            {t.questionnaire.next}
          </button>
        )}
      </div>
    </section>
  );
}
