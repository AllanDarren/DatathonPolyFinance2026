// Authentification : un client (Cognito en production, local pour le développement et les tests)
// et des jetons. Le mot de passe ne quitte le navigateur que vers Cognito, en HTTPS ; il n'est jamais stocké.

export type Tokens = {
  accessToken: string; // envoyé à notre API (Authorization: Bearer)
  idToken: string | null;
  refreshToken: string | null; // conservé seulement si « rester connecté », sinon pour l'onglet en cours
  expiresAt: number; // ms depuis epoch, expiration du jeton d'accès
};

export type SessionUser = { email: string; sub: string };

export interface AuthClient {
  readonly kind: 'cognito' | 'local';
  signUp(email: string, password: string): Promise<void>;
  signIn(email: string, password: string): Promise<{ tokens: Tokens; user: SessionUser }>;
  refresh(refreshToken: string, user: SessionUser): Promise<Tokens>;
  signOut(tokens: Tokens): Promise<void>;
}

/** Erreur d'authentification avec un message déjà lisible (français). */
export class AuthError extends Error {
  readonly code: string;
  constructor(code: string, message: string) {
    super(message);
    this.name = 'UserError'; // affichée telle quelle par userMessage()
    this.code = code;
  }
}
