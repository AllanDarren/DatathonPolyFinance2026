// Authentification LOCALE : développement (make dev) et tests seulement, jamais déployée.
// Comptes en mémoire de l'onglet ; le mot de passe est comparé via une empreinte SHA-256 salée
// (jamais conservé en clair). Le jeton « local.<id> » n'est accepté que par api/local_server.py.
import { AUTH_MSG } from './messages';
import { AuthError, type AuthClient, type SessionUser, type Tokens } from './types';

async function digest(salt: string, password: string): Promise<string> {
  const data = new TextEncoder().encode(`${salt}:${password}`);
  if (globalThis.crypto?.subtle) {
    const buf = await globalThis.crypto.subtle.digest('SHA-256', data);
    return [...new Uint8Array(buf)].map((b) => b.toString(16).padStart(2, '0')).join('');
  }
  return `${salt}:${password.length}`; // environnement sans Web Crypto (ne concerne que des tests anciens)
}

/** Identifiant stable et sûr pour une URL/clé, dérivé du courriel. */
export function localUserId(email: string): string {
  return `local-${email.trim().toLowerCase().replace(/[^a-z0-9._@+-]/g, '_')}`.slice(0, 120);
}

export function localClient(): AuthClient {
  const accounts = new Map<string, { salt: string; hash: string }>();
  const DAY = 24 * 3600 * 1000;

  const tokensFor = (user: SessionUser): Tokens => ({
    accessToken: `local.${user.sub}`,
    idToken: null,
    refreshToken: `local-refresh.${user.sub}`,
    expiresAt: Date.now() + DAY,
  });

  return {
    kind: 'local',
    async signUp(email, password) {
      const key = email.trim().toLowerCase();
      if (accounts.has(key)) throw new AuthError('EMAIL_TAKEN', AUTH_MSG.emailTaken);
      const salt = Math.random().toString(36).slice(2);
      accounts.set(key, { salt, hash: await digest(salt, password) });
    },
    async signIn(email, password) {
      const key = email.trim().toLowerCase();
      const acc = accounts.get(key);
      if (!acc || acc.hash !== (await digest(acc.salt, password))) {
        throw new AuthError('BAD_CREDENTIALS', AUTH_MSG.badCredentials);
      }
      const user = { email: key, sub: localUserId(key) };
      return { tokens: tokensFor(user), user };
    },
    async refresh(_refreshToken, user) {
      return tokensFor(user);
    },
    async signOut() {},
  };
}
