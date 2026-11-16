import { AuthError } from './types';

export const AUTH_MSG = {
  emailRequired: 'Indique ton courriel.',
  emailInvalid: 'Ce courriel n’est pas valide.',
  passwordRequired: 'Indique ton mot de passe.',
  passwordWeak: 'Mot de passe trop faible : au moins 8 caractères, avec une majuscule, une minuscule et un chiffre.',
  passwordMismatch: 'Les deux mots de passe ne correspondent pas.',
  emailTaken: 'Un compte existe déjà avec ce courriel. Connecte-toi plutôt.',
  badCredentials: 'Courriel ou mot de passe incorrect.',
  tooMany: 'Trop de tentatives. Réessaie dans quelques minutes.',
  notConfirmed: 'Ce compte n’est pas encore confirmé.',
  network: 'Impossible de joindre le service de connexion. Vérifie ta connexion internet.',
  sessionExpired: 'Ta session a expiré. Reconnecte-toi.',
  generic: 'La connexion a échoué. Réessaie dans un instant.',
};

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** Validation côté navigateur, avant tout appel (même politique que le pool Cognito). */
export function validateCredentials(email: string, password: string, confirm?: string): string | null {
  if (!email.trim()) return AUTH_MSG.emailRequired;
  if (!EMAIL_RE.test(email.trim())) return AUTH_MSG.emailInvalid;
  if (!password) return AUTH_MSG.passwordRequired;
  if (confirm !== undefined) {
    if (password.length < 8 || !/[a-z]/.test(password) || !/[A-Z]/.test(password) || !/[0-9]/.test(password)) {
      return AUTH_MSG.passwordWeak;
    }
    if (password !== confirm) return AUTH_MSG.passwordMismatch;
  }
  return null;
}

/** Erreurs Cognito (`__type`) -> message français. */
export function cognitoError(type: string, message = ''): AuthError {
  const t = type.split('#').pop() ?? type;
  switch (t) {
    case 'UsernameExistsException':
    case 'AliasExistsException':
      return new AuthError('EMAIL_TAKEN', AUTH_MSG.emailTaken);
    case 'NotAuthorizedException':
    case 'UserNotFoundException':
      return new AuthError('BAD_CREDENTIALS', AUTH_MSG.badCredentials);
    case 'InvalidPasswordException':
      return new AuthError('WEAK_PASSWORD', AUTH_MSG.passwordWeak);
    case 'InvalidParameterException':
      return /password/i.test(message)
        ? new AuthError('WEAK_PASSWORD', AUTH_MSG.passwordWeak)
        : new AuthError('INVALID_EMAIL', AUTH_MSG.emailInvalid);
    case 'TooManyRequestsException':
    case 'LimitExceededException':
    case 'TooManyFailedAttemptsException':
      return new AuthError('TOO_MANY', AUTH_MSG.tooMany);
    case 'UserNotConfirmedException':
      return new AuthError('NOT_CONFIRMED', AUTH_MSG.notConfirmed);
    default:
      return new AuthError('AUTH_FAILED', AUTH_MSG.generic);
  }
}
