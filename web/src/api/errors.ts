import { t } from '../strings';

/** Erreur de l'API au format {error: {code, message, details?}}. */
export class ApiRequestError extends Error {
  readonly code: string;
  readonly status: number;
  readonly details?: unknown;

  constructor(code: string, message: string, status = 0, details?: unknown) {
    super(message);
    this.name = 'ApiRequestError';
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

/** Message lisible pour l'utilisateur. */
export function userMessage(err: unknown): string {
  if (err instanceof ApiRequestError) {
    return t.errors.codes[err.code] ?? (err.message || t.errors.generic);
  }
  if (err instanceof Error && err.name === 'UserError') return err.message;
  if (err instanceof TypeError) return t.errors.network;
  return t.errors.generic;
}

/** Erreur côté interface dont le message est déjà lisible pour l'utilisateur. */
export class UserError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'UserError';
  }
}
