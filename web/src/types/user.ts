// Données du compte (routes /me de l'API). Hors des contrats de A : couche de stockage par utilisateur.
import type { FeedResponse, Portfolio, Profile } from './contracts';

export type BriefMeta = {
  brief_id: string;
  saved_at: string;
  generated_at: string | null;
  data_as_of: string | null;
  news_as_of: string | null;
  profile_label: string | null;
  shown: number;
  hidden: number;
};

export type MeState = {
  profile: Profile | null;
  persona_id: string | null;
  profile_updated_at: string | null;
  portfolio: Portfolio | null;
  portfolio_csv: string | null;
  portfolio_updated_at: string | null;
  briefs: BriefMeta[];
};

export interface MeApi {
  get(token: string): Promise<MeState>;
  saveProfile(token: string, profile: Profile, personaId: string | null): Promise<void>;
  savePortfolio(token: string, csv: string): Promise<Portfolio>;
  saveBrief(token: string, feed: FeedResponse): Promise<BriefMeta>;
  getBrief(token: string, briefId: string): Promise<FeedResponse>;
  deleteAll(token: string): Promise<void>;
}
