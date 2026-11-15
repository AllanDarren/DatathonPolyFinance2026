// Types des contrats v0 (section 8 de CLAUDE.md / contexte commun).
// Provisoire : dès que le rôle A publie contracts/*.schema.json, `npm run gen:types`
// génère src/types/generated/ et ce fichier ne fera que ré-exporter ces types.
// Ne pas modifier à la main sans passer par la procédure « [contract] ».

export type RiskTolerance = 'low' | 'low_moderate' | 'moderate' | 'high';
export type HorizonBucket = 'short' | 'medium' | 'long';
export type HorizonRelevance = 'structural' | 'macro_context' | 'short_term_noise';
export type AssetClass = 'equity_ca' | 'equity_us' | 'bond_etf' | 'equity_etf' | 'gold_etf' | 'crypto';

export type Profile = {
  profile_id: string;
  label: string;
  source: 'persona_preset' | 'questionnaire';
  age?: number;
  horizon_years: number;
  horizon_bucket: HorizonBucket;
  risk_tolerance: RiskTolerance;
  max_acceptable_loss_pct: number;
  objective: 'capital_preservation' | 'income' | 'balanced' | 'growth';
  experience: 'beginner' | 'intermediate' | 'advanced';
  preferences: { avoid_controversies: boolean; excluded_sectors: string[]; interests: string[] };
  limits: { max_single_position: number; max_high_vol_share: number };
  monthly_expenses_cad: number | null;
  base_currency: 'CAD';
  inconsistencies: string[];
};

export type Persona = { id: string; label: string; profile: Profile; sample_portfolio_csv: string };

export type Position = {
  ticker: string;
  amount: number;
  weight: number;
  asset_class: AssetClass;
  price_currency: 'CAD' | 'USD';
  in_universe: boolean;
};

export type Portfolio = {
  base_currency: 'CAD';
  total_amount: number;
  positions: Position[];
  unanalyzed: { tickers: string[]; weight: number };
  warnings: string[];
};

export type Consideration = { ticker: string; intended_weight: number };

export type EventType = 'earnings' | 'dividend_ex_date' | 'rate_decision' | 'cpi_release' | 'other';

export type Event = {
  id: string;
  type: EventType;
  scope: 'ticker' | 'macro';
  tickers: string[];
  date: string;
  title: string;
  is_estimated: boolean;
  source: string;
  retrieved_at: string;
};

export type EvidenceKind = 'metric' | 'rule_hit' | 'classification' | 'event_study' | 'portfolio_calc' | 'news_source';

export type Evidence = {
  id: string;
  kind: EvidenceKind;
  statement: string;
  value: number | string | null;
  unit: string | null;
  as_of: string;
  inputs: Record<string, unknown>;
  source: string;
  computed_by: string;
};

export type ClaimLabel = 'fact' | 'hypothesis' | 'scenario';

export type Claim = {
  text: string;
  label: ClaimLabel;
  evidence_ids: string[];
  verified: 'supported' | 'unsupported' | 'not_checked';
};

export type Explanation = {
  summary: string;
  claims: Claim[];
  generated_by: 'bedrock' | 'template';
  guardian: { status: 'passed' | 'flagged' | 'not_run'; flags: string[] };
};

export type RuleHit = {
  rule_id: string;
  text: string;
  delta?: number;
  observed?: number;
  limit?: number;
  severity?: 'low' | 'medium' | 'high';
};

export type HistoricalContext = {
  event_type: EventType;
  asset: string;
  window: string;
  n_events: number;
  median_return: number;
  p10: number;
  p90: number;
  share_positive: number;
  events: { date: string; return: number }[];
  caveats: string[];
  evidence_id: string;
};

export type CoherenceResult = {
  verdict: 'coherent' | 'tension' | 'incoherent';
  rule_hits: RuleHit[];
  metrics: {
    annualized_vol: number;
    max_drawdown: number;
    worst_calendar_year_return: number;
    position_weight_after: number;
  };
  explanation: Explanation;
};

export type RelevanceLevel = 'high' | 'medium' | 'low';

export type FeedItem = {
  news_id: string;
  title: string;
  url: string;
  source: string;
  published_at: string;
  tickers: string[];
  is_synthetic: boolean;
  category: string;
  horizon_relevance: HorizonRelevance;
  relevance: {
    score: number;
    level: RelevanceLevel;
    shown: boolean;
    position_weight: number;
    rule_hits: RuleHit[];
  };
  explanation: Explanation;
  historical_context: HistoricalContext | null;
};

export type FeedResponse = {
  generated_at: string;
  data_as_of: string;
  news_as_of: string;
  profile: Profile;
  portfolio_summary: {
    top_positions: Position[];
    asset_class_weights: Record<string, number>;
    high_vol_share: number;
    top3_concentration: number;
  };
  items: FeedItem[];
  hidden: { count: number; by_reason: { reason: string; count: number }[] };
  coherence: CoherenceResult | null;
  events: Event[];
  evidence: Record<string, Evidence>;
  disclaimers: string[];
  limits: string[];
};

export type ApiError = { error: { code: string; message: string; details?: unknown } };

export type Health = { status: string; version: string; llm_provider: string };

// rules/questionnaire.yaml servi en JSON par GET /questionnaire
export type QuestionOption = {
  id: string;
  label: string;
  points?: Record<string, number>;
  sets?: Record<string, unknown>;
};
export type Question = { id: string; text: string; help?: string; options: QuestionOption[] };
export type Questionnaire = { version: number; questions: Question[] };

// rules/glossary.yaml
export type GlossaryTerm = { id: string; term: string; definition_fr: string };
export type Glossary = { terms: GlossaryTerm[] };
