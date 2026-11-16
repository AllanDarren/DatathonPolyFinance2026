// Persistance de la session. Seuls l'adresse, l'identifiant et le jeton de rafraîchissement sont gardés :
// jamais le mot de passe, jamais le portefeuille (celui-ci est sur le serveur, lié au compte).
// - « Rester connecté » : localStorage, au plus SESSION_DAYS jours (Cognito borne aussi le jeton à 30 jours).
// - Sinon : sessionStorage, effacé à la fermeture de l'onglet.
import type { SessionUser } from './types';

const KEY = 'alphaforge.session';
export const SESSION_DAYS = 30;

export type StoredSession = { user: SessionUser; refreshToken: string; remember: boolean; until: number };

function stores(): Storage[] {
  const out: Storage[] = [];
  try {
    out.push(window.localStorage);
  } catch {
    /* stockage bloqué (navigation privée) : la session reste en mémoire */
  }
  try {
    out.push(window.sessionStorage);
  } catch {
    /* idem */
  }
  return out;
}

export function loadSession(): StoredSession | null {
  for (const s of stores()) {
    try {
      const raw = s.getItem(KEY);
      if (!raw) continue;
      const v = JSON.parse(raw) as StoredSession;
      if (v?.refreshToken && v.user?.email && v.until > Date.now()) return v;
      s.removeItem(KEY);
    } catch {
      /* valeur illisible : ignorée */
    }
  }
  return null;
}

export function saveSession(user: SessionUser, refreshToken: string, remember: boolean): void {
  clearSession();
  const until = remember ? Date.now() + SESSION_DAYS * 24 * 3600 * 1000 : Date.now() + 24 * 3600 * 1000;
  const value = JSON.stringify({ user, refreshToken, remember, until } satisfies StoredSession);
  try {
    (remember ? window.localStorage : window.sessionStorage).setItem(KEY, value);
  } catch {
    /* stockage indisponible : la session durera le temps de la page */
  }
}

export function clearSession(): void {
  for (const s of stores()) {
    try {
      s.removeItem(KEY);
    } catch {
      /* rien */
    }
  }
}
