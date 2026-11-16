import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { defaultAuthClient } from './config';
import { validateCredentials } from './messages';
import { clearSession, loadSession, saveSession } from './session';
import { AuthError, type AuthClient, type SessionUser, type Tokens } from './types';

type Status = 'loading' | 'signedOut' | 'signedIn';

type AuthValue = {
  status: Status;
  user: SessionUser | null;
  kind: AuthClient['kind'];
  signUp: (email: string, password: string, confirm: string, remember: boolean) => Promise<void>;
  signIn: (email: string, password: string, remember: boolean) => Promise<void>;
  signOut: () => Promise<void>;
  /** Jeton d'accès valide (renouvelé si besoin), ou null si la session a expiré. */
  getAccessToken: () => Promise<string | null>;
};

const Ctx = createContext<AuthValue | null>(null);

export function AuthProvider({ children, client }: { children: ReactNode; client?: AuthClient }) {
  const auth = useMemo(() => client ?? defaultAuthClient(), [client]);
  const [status, setStatus] = useState<Status>('loading');
  const [user, setUser] = useState<SessionUser | null>(null);
  const tokens = useRef<Tokens | null>(null);
  const remember = useRef(false);

  const endSession = useCallback(() => {
    tokens.current = null;
    clearSession();
    setUser(null);
    setStatus('signedOut');
  }, []);

  // Reprise de session au chargement : jeton de rafraîchissement -> nouveau jeton d'accès.
  useEffect(() => {
    const saved = loadSession();
    if (!saved) {
      setStatus('signedOut');
      return;
    }
    let alive = true;
    auth.refresh(saved.refreshToken, saved.user).then(
      (tk) => {
        if (!alive) return;
        tokens.current = tk;
        remember.current = saved.remember;
        setUser(saved.user);
        setStatus('signedIn');
      },
      () => alive && endSession(),
    );
    return () => {
      alive = false;
    };
  }, [auth, endSession]);

  const start = useCallback((tk: Tokens, u: SessionUser, keep: boolean) => {
    tokens.current = tk;
    remember.current = keep;
    if (tk.refreshToken) saveSession(u, tk.refreshToken, keep);
    setUser(u);
    setStatus('signedIn');
  }, []);

  const signIn = useCallback(
    async (email: string, password: string, keep: boolean) => {
      const err = validateCredentials(email, password);
      if (err) throw new AuthError('INVALID_INPUT', err);
      const { tokens: tk, user: u } = await auth.signIn(email.trim().toLowerCase(), password);
      start(tk, u, keep);
    },
    [auth, start],
  );

  const signUp = useCallback(
    async (email: string, password: string, confirm: string, keep: boolean) => {
      const err = validateCredentials(email, password, confirm);
      if (err) throw new AuthError('INVALID_INPUT', err);
      const e = email.trim().toLowerCase();
      await auth.signUp(e, password);
      const { tokens: tk, user: u } = await auth.signIn(e, password);
      start(tk, u, keep);
    },
    [auth, start],
  );

  const signOut = useCallback(async () => {
    const tk = tokens.current;
    endSession();
    if (tk) await auth.signOut(tk);
  }, [auth, endSession]);

  const getAccessToken = useCallback(async () => {
    const tk = tokens.current;
    if (!tk || !user) return null;
    if (tk.expiresAt - 60_000 > Date.now()) return tk.accessToken;
    if (!tk.refreshToken) {
      endSession();
      return null;
    }
    try {
      tokens.current = await auth.refresh(tk.refreshToken, user);
      return tokens.current.accessToken;
    } catch {
      endSession();
      return null;
    }
  }, [auth, user, endSession]);

  const value = useMemo<AuthValue>(
    () => ({ status, user, kind: auth.kind, signUp, signIn, signOut, getAccessToken }),
    [status, user, auth.kind, signUp, signIn, signOut, getAccessToken],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthValue {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth doit être utilisé dans <AuthProvider>');
  return v;
}
