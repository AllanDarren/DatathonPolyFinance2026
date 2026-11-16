// Connexion / création de compte (Amazon Cognito). Messages d'erreur en français, sous le formulaire.
import { useId, useState, type FormEvent } from 'react';
import { userMessage } from '../api/errors';
import { useAuth } from '../auth/AuthProvider';
import { t } from '../strings';

type Mode = 'signIn' | 'signUp';

export function AuthScreen({ initialMode = 'signIn' }: { initialMode?: Mode }) {
  const auth = useAuth();
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const errId = useId();
  const A = t.auth;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === 'signIn') await auth.signIn(email, password, remember);
      else await auth.signUp(email, password, confirm, remember);
    } catch (err) {
      setError(userMessage(err));
      setBusy(false);
    }
  }

  function switchTo(m: Mode) {
    setMode(m);
    setError(null);
    setPassword('');
    setConfirm('');
  }

  return (
    <section className="panel narrow auth" aria-labelledby="auth-title">
      <div className="auth-tabs" role="tablist" aria-label={A.title}>
        <button type="button" role="tab" aria-selected={mode === 'signIn'} className={mode === 'signIn' ? 'on' : ''} onClick={() => switchTo('signIn')}>
          {A.signInTab}
        </button>
        <button type="button" role="tab" aria-selected={mode === 'signUp'} className={mode === 'signUp' ? 'on' : ''} onClick={() => switchTo('signUp')}>
          {A.signUpTab}
        </button>
      </div>
      <h1 id="auth-title" className="auth-title">{mode === 'signIn' ? A.signInTitle : A.signUpTitle}</h1>
      <p className="muted small">{mode === 'signIn' ? A.signInLead : A.signUpLead}</p>

      <form className="auth-form" onSubmit={submit} noValidate aria-describedby={error ? errId : undefined}>
        <label>
          <span>{A.email}</span>
          <input type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="toi@exemple.com" />
        </label>
        <label>
          <span>{A.password}</span>
          <input
            type="password"
            autoComplete={mode === 'signIn' ? 'current-password' : 'new-password'}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {mode === 'signUp' && (
          <>
            <p className="small muted">{A.passwordRule}</p>
            <label>
              <span>{A.confirm}</span>
              <input type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            </label>
          </>
        )}
        <label className="check">
          <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
          <span>{A.remember}</span>
        </label>
        {error && <p id={errId} className="form-error" role="alert">{error}</p>}
        <button type="submit" className="btn btn-primary" disabled={busy}>
          {busy ? A.busy : mode === 'signIn' ? A.signInSubmit : A.signUpSubmit}
        </button>
      </form>

      <p className="small muted auth-foot">
        {mode === 'signIn' ? A.noAccount : A.hasAccount}{' '}
        <button type="button" className="link-btn" onClick={() => switchTo(mode === 'signIn' ? 'signUp' : 'signIn')}>
          {mode === 'signIn' ? A.signUpTab : A.signInTab}
        </button>
      </p>
      <p className="small muted">{A.privacy}</p>
      {auth.kind === 'local' && <p className="small muted">{A.localMode}</p>}
    </section>
  );
}
