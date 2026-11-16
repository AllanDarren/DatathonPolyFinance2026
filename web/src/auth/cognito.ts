// Client Amazon Cognito (User Pool) sans SDK : appels JSON à l'API publique cognito-idp.
// Client d'application public (sans secret) ; flux USER_PASSWORD_AUTH en HTTPS, puis REFRESH_TOKEN_AUTH.
import { jwtPayload } from './jwt';
import { AUTH_MSG, cognitoError } from './messages';
import { AuthError, type AuthClient, type SessionUser, type Tokens } from './types';

type AuthResult = { AccessToken: string; IdToken?: string; RefreshToken?: string; ExpiresIn: number };

export function cognitoClient(region: string, clientId: string): AuthClient {
  const endpoint = `https://cognito-idp.${region}.amazonaws.com/`;

  async function call<T>(action: string, body: Record<string, unknown>): Promise<T> {
    let res: Response;
    try {
      res = await fetch(endpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/x-amz-json-1.1',
          'X-Amz-Target': `AWSCognitoIdentityProviderService.${action}`,
        },
        body: JSON.stringify(body),
      });
    } catch {
      throw new AuthError('NETWORK', AUTH_MSG.network);
    }
    const data = (await res.json().catch(() => ({}))) as Record<string, unknown>;
    if (!res.ok) throw cognitoError(String(data.__type ?? ''), String(data.message ?? ''));
    return data as T;
  }

  const toTokens = (r: AuthResult, refreshToken: string | null): Tokens => ({
    accessToken: r.AccessToken,
    idToken: r.IdToken ?? null,
    refreshToken: r.RefreshToken ?? refreshToken,
    expiresAt: Date.now() + r.ExpiresIn * 1000,
  });

  return {
    kind: 'cognito',
    async signUp(email, password) {
      await call('SignUp', {
        ClientId: clientId,
        Username: email,
        Password: password,
        UserAttributes: [{ Name: 'email', Value: email }],
      });
    },
    async signIn(email, password) {
      const out = await call<{ AuthenticationResult?: AuthResult; ChallengeName?: string }>('InitiateAuth', {
        AuthFlow: 'USER_PASSWORD_AUTH',
        ClientId: clientId,
        AuthParameters: { USERNAME: email, PASSWORD: password },
      });
      if (!out.AuthenticationResult) throw new AuthError('CHALLENGE', AUTH_MSG.generic);
      const tokens = toTokens(out.AuthenticationResult, null);
      const claims = jwtPayload(tokens.idToken ?? tokens.accessToken);
      const user: SessionUser = { email: String(claims.email ?? email), sub: String(claims.sub ?? '') };
      return { tokens, user };
    },
    async refresh(refreshToken) {
      try {
        const out = await call<{ AuthenticationResult: AuthResult }>('InitiateAuth', {
          AuthFlow: 'REFRESH_TOKEN_AUTH',
          ClientId: clientId,
          AuthParameters: { REFRESH_TOKEN: refreshToken },
        });
        return toTokens(out.AuthenticationResult, refreshToken);
      } catch (e) {
        if (e instanceof AuthError && e.code === 'BAD_CREDENTIALS') throw new AuthError('EXPIRED', AUTH_MSG.sessionExpired);
        throw e;
      }
    },
    async signOut(tokens) {
      // Révoque le jeton de rafraîchissement : la session ne peut plus être prolongée, même volée.
      if (tokens.refreshToken) {
        await call('RevokeToken', { ClientId: clientId, Token: tokens.refreshToken }).catch(() => undefined);
      }
    },
  };
}
