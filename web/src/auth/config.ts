import { cognitoClient } from './cognito';
import { localClient } from './local';
import type { AuthClient } from './types';

// VITE_AUTH=cognito (déploiement) avec VITE_COGNITO_REGION et VITE_COGNITO_CLIENT_ID (identifiants publics,
// pas des secrets : sorties de la pile CloudFormation). Sinon : authentification locale de développement.
const region = (import.meta.env.VITE_COGNITO_REGION as string | undefined) ?? '';
const clientId = (import.meta.env.VITE_COGNITO_CLIENT_ID as string | undefined) ?? '';
const mode = (import.meta.env.VITE_AUTH as string | undefined) ?? (clientId ? 'cognito' : 'local');

export const AUTH_MODE: 'cognito' | 'local' = mode === 'cognito' && region && clientId ? 'cognito' : 'local';

export function defaultAuthClient(): AuthClient {
  return AUTH_MODE === 'cognito' ? cognitoClient(region, clientId) : localClient();
}
