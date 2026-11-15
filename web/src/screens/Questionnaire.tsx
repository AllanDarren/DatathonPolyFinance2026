// Questionnaire piloté par les données (GET /questionnaire) : aucune question codée en dur.
// Dernière étape facultative : une note libre. L'agent propose des préférences (avec la citation
// exacte de la note); rien n'est appliqué sans confirmation, et le risque ou l'horizon ne changent jamais.
import { useState } from 'react';
import { api } from '../api/client';
import { ErrorBox, Skeleton } from '../components/Feedback';
import { useAsync } from '../lib/useAsync';
import { useApp } from '../state/store';
import { t } from '../strings';
import type { ConfirmedPreferences, PreferenceExtraction } from '../types/contracts';

const NOTE_MAX = 300;

export function Questionnaire() {
  const { setProfile, go } = useApp();
  const q = useAsync(() => api.getQuestionnaire(), []);
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [note, setNote] = useState('');
  const [extraction, setExtraction] = useState<PreferenceExtraction | null>(null);
  const [checked, setChecked] = useState<Record<number, boolean>>({});
  const [analyzing, setAnalyzing] = useState(false);

  if (q.loading) return <Skeleton lines={4} label="Chargement du questionnaire…" />;
  if (q.error || !q.data) return <ErrorBox error={q.error} onRetry={q.reload} />;

  const questions = q.data.questions;
  const total = questions.length + 1; // + la note libre
  const onNote = index === questions.length;
  const question = questions[index];

  function confirmed(): ConfirmedPreferences | null {
    if (!extraction) return null;
    const keep = extraction.suggestions.filter((_, i) => checked[i]);
    if (keep.length === 0) return null;
    return {
      excluded_sectors: keep.filter((s) => s.field === 'excluded_sectors').map((s) => String(s.value)),
      interests: keep.filter((s) => s.field === 'interests').map((s) => String(s.value)),
      avoid_controversies: keep.some((s) => s.field === 'avoid_controversies') ? true : null,
    };
  }

  async function analyze() {
    setAnalyzing(true);
    setError(null);
    try {
      const x = await api.extractPreferences(note);
      setExtraction(x);
      setChecked(Object.fromEntries(x.suggestions.map((_, i) => [i, true])));
    } catch (e) {
      setError(e);
    } finally {
      setAnalyzing(false);
    }
  }

  async function submit() {
    setSubmitting(true);
    setError(null);
    try {
      setProfile(await api.scoreProfile(answers, confirmed()));
      go('profile');
    } catch (e) {
      setError(e);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className="panel narrow questionnaire" aria-labelledby="q-title">
      <p className="eyebrow">{t.questionnaire.title} · {t.questionnaire.progress(index + 1, total)}</p>
      <div className="progress" aria-hidden="true">
        <div className="progress-fill" style={{ width: `${((index + 1) / total) * 100}%` }} />
      </div>

      {!onNote && question && (
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
      )}

      {onNote && (
        <div className="note-step">
          <label htmlFor="note" id="q-title" className="q-text">{t.questionnaire.noteTitle}</label>
          <p className="muted small">{t.questionnaire.noteHelp}</p>
          <textarea
            id="note"
            rows={3}
            maxLength={NOTE_MAX}
            value={note}
            placeholder={t.questionnaire.notePlaceholder}
            onChange={(e) => {
              setNote(e.target.value);
              setExtraction(null);
            }}
          />
          <p className="small muted row-between">
            <span>{t.questionnaire.notePrivacy}</span>
            <span>{note.length}/{NOTE_MAX}</span>
          </p>
          <button type="button" className="btn btn-secondary" disabled={!note.trim() || analyzing} onClick={analyze}>
            {analyzing ? t.questionnaire.noteAnalyzing : t.questionnaire.noteAnalyze}
          </button>
          {extraction && (
            <div className="note-result" aria-live="polite">
              {extraction.suggestions.length === 0 ? (
                <p className="small">{t.questionnaire.noteNothing}</p>
              ) : (
                <>
                  <p className="small"><strong>{t.questionnaire.noteUnderstood}</strong></p>
                  <ul className="plain">
                    {extraction.suggestions.map((s, i) => (
                      <li key={i}>
                        <label className="check">
                          <input
                            type="checkbox"
                            checked={Boolean(checked[i])}
                            onChange={(e) => setChecked((c) => ({ ...c, [i]: e.target.checked }))}
                          />
                          <span>{s.label_fr} <span className="muted small">— « {s.quote} »</span></span>
                        </label>
                      </li>
                    ))}
                  </ul>
                </>
              )}
              <p className="callout small">{extraction.notice_fr}</p>
            </div>
          )}
        </div>
      )}

      {error ? <ErrorBox error={error} /> : null}
      <div className="row-between">
        <button type="button" className="btn btn-secondary" disabled={index === 0} onClick={() => setIndex((i) => i - 1)}>
          {t.questionnaire.previous}
        </button>
        {onNote ? (
          <button type="button" className="btn btn-primary" disabled={submitting} onClick={submit}>
            {t.questionnaire.finish}
          </button>
        ) : (
          <button
            type="button"
            className="btn btn-primary"
            disabled={!question || (!answers[question.id] && !question.optional)}
            onClick={() => setIndex((i) => i + 1)}
          >
            {t.questionnaire.next}
          </button>
        )}
      </div>
    </section>
  );
}
