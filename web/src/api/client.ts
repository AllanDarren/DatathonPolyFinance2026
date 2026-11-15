// Client typé de l'API (endpoints de la section 8). En mode simulé, sert src/api/mock.
import type {
  ConfirmedPreferences, Consideration, Event, FeedResponse, Health, Persona, Portfolio, PreferenceExtraction, Profile,
  Questionnaire,
} from '../types/contracts';
import { API_URL, IS_MOCK } from './config';
import { ApiRequestError } from './errors';
import { mockApi } from './mock/mockApi';

export interface Api {
  health(): Promise<Health>;
  getQuestionnaire(): Promise<Questionnaire>;
  getPersonas(): Promise<Persona[]>;
  scoreProfile(answers: Record<string, string>, confirmed?: ConfirmedPreferences | null): Promise<Profile>;
  extractPreferences(text: string): Promise<PreferenceExtraction>;
  parsePortfolio(csv: string): Promise<Portfolio>;
  buildFeed(profile: Profile, portfolio: Portfolio, consideration?: Consideration | null): Promise<FeedResponse>;
  getEvents(tickers?: string[]): Promise<Event[]>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
  });
  const text = await res.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    throw new ApiRequestError('BAD_RESPONSE', 'Réponse illisible de l’API.', res.status);
  }
  if (!res.ok) {
    const e = (body as { error?: { code?: string; message?: string; details?: unknown } } | null)?.error;
    throw new ApiRequestError(e?.code ?? `HTTP_${res.status}`, e?.message ?? res.statusText, res.status, e?.details);
  }
  return body as T;
}

const post = <T>(path: string, payload: unknown) => request<T>(path, { method: 'POST', body: JSON.stringify(payload) });

export const httpApi: Api = {
  health: () => request('/health'),
  getQuestionnaire: () => request('/questionnaire'),
  getPersonas: () => request('/personas'),
  scoreProfile: (answers, confirmed) =>
    post('/profile', confirmed ? { answers, confirmed_preferences: confirmed } : { answers }),
  extractPreferences: (text) => post('/preferences/extract', { text }),
  parsePortfolio: (csv) => post('/portfolio/parse', { csv }),
  buildFeed: (profile, portfolio, consideration) =>
    post('/feed', consideration ? { profile, portfolio, consideration } : { profile, portfolio }),
  getEvents: (tickers) =>
    request(tickers && tickers.length ? `/events?tickers=${encodeURIComponent(tickers.join(','))}` : '/events'),
};

export const api: Api = IS_MOCK ? mockApi : httpApi;
