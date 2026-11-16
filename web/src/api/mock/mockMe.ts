// Faux stockage par compte pour les tests (Vitest) : en mémoire, indexé par le jeton local.
import type { FeedResponse, Portfolio, Profile } from '../../types/contracts';
import type { BriefMeta, MeApi, MeState } from '../../types/user';
import { ApiRequestError } from '../errors';
import { mockApi } from './mockApi';

type Account = { profile: Profile | null; personaId: string | null; csv: string | null; portfolio: Portfolio | null; briefs: { meta: BriefMeta; feed: FeedResponse }[] };
const accounts = new Map<string, Account>();

function account(token: string): Account {
  if (!token.startsWith('local.')) throw new ApiRequestError('UNAUTHORIZED', 'Connexion requise.', 401);
  let a = accounts.get(token);
  if (!a) {
    a = { profile: null, personaId: null, csv: null, portfolio: null, briefs: [] };
    accounts.set(token, a);
  }
  return a;
}

const clone = <T>(v: T): T => structuredClone(v);

export const mockMeApi: MeApi = {
  async get(token) {
    const a = account(token);
    const state: MeState = {
      profile: a.profile, persona_id: a.personaId, profile_updated_at: null,
      portfolio: a.portfolio, portfolio_csv: a.csv, portfolio_updated_at: null,
      briefs: a.briefs.map((b) => b.meta),
    };
    return clone(state);
  },
  async saveProfile(token, profile, personaId) {
    Object.assign(account(token), { profile: clone(profile), personaId });
  },
  async savePortfolio(token, csv) {
    const portfolio = await mockApi.parsePortfolio(csv);
    Object.assign(account(token), { csv, portfolio: clone(portfolio) });
    return portfolio;
  },
  async saveBrief(token, feed) {
    const a = account(token);
    const meta: BriefMeta = {
      brief_id: `b${a.briefs.length + 1}`, saved_at: new Date().toISOString(), generated_at: feed.generated_at,
      data_as_of: feed.data_as_of, news_as_of: feed.news_as_of, profile_label: feed.profile.label,
      shown: feed.items.filter((i) => i.relevance.shown).length, hidden: feed.hidden.count,
    };
    a.briefs = [{ meta, feed: clone(feed) }, ...a.briefs].slice(0, 10);
    return meta;
  },
  async getBrief(token, id) {
    const b = account(token).briefs.find((x) => x.meta.brief_id === id);
    if (!b) throw new ApiRequestError('NOT_FOUND', 'Brief introuvable.', 404);
    return clone(b.feed);
  },
  async deleteAll(token) {
    accounts.delete(token);
  },
};

/** Tests : repartir de zéro. */
export function resetMockAccounts(): void {
  accounts.clear();
}
