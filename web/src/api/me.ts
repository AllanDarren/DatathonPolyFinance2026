// Client des routes /me : chaque appel porte le jeton d'accès (vérifié par API Gateway en production).
import type { FeedResponse, Portfolio } from '../types/contracts';
import type { BriefMeta, MeApi, MeState } from '../types/user';
import { API_URL, IS_MOCK } from './config';
import { ApiRequestError } from './errors';
import { mockMeApi } from './mock/mockMe';

async function call<T>(token: string, method: string, path: string, payload?: unknown): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    method,
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
    body: payload === undefined ? undefined : JSON.stringify(payload),
  });
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    throw new ApiRequestError('BAD_RESPONSE', 'Réponse illisible de l’API.', res.status);
  }
  if (!res.ok) {
    const e = (body as { error?: { code?: string; message?: string } } | null)?.error;
    // API Gateway répond {"message":"Unauthorized"} sans notre format quand le jeton est refusé.
    const code = e?.code ?? (res.status === 401 ? 'UNAUTHORIZED' : `HTTP_${res.status}`);
    throw new ApiRequestError(code, e?.message ?? res.statusText, res.status);
  }
  return body as T;
}

export const httpMeApi: MeApi = {
  get: (token) => call<MeState>(token, 'GET', '/me'),
  saveProfile: async (token, profile, personaId) => {
    await call(token, 'PUT', '/me/profile', { profile, persona_id: personaId });
  },
  savePortfolio: async (token, csv) => (await call<{ portfolio: Portfolio }>(token, 'PUT', '/me/portfolio', { csv })).portfolio,
  saveBrief: (token, feed) => call<BriefMeta>(token, 'POST', '/me/briefs', { feed }),
  getBrief: (token, id) => call<FeedResponse>(token, 'GET', `/me/briefs/${encodeURIComponent(id)}`),
  deleteAll: async (token) => {
    await call(token, 'DELETE', '/me');
  },
};

export const meApi: MeApi = IS_MOCK ? mockMeApi : httpMeApi;
