// Types des contrats v0 (miroir des JSON Schemas de contracts/).
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
  confirmed_from_note?: string[]; // v0.3.0 : préférences tirées de la note libre, confirmées
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

export type Verdict = 'coherent' | 'tension' | 'incoherent';

// v0.3.0 : couche multi-agents (tous les champs sont optionnels)
export type ToolCall = {
  step: number;
  tool: string;
  params: Record<string, unknown>;
  evidence_ids: string[];
  status: 'ok' | 'error';
  forced: boolean;
  planner: string; // id du modèle, 'mock' hors ligne, 'code' pour une étape exécutée par le code
  duration_ms: number;
  error?: string | null;
};

export type DiversificationImpact = {
  ticker: string;
  verdict: 'new_exposure' | 'partial' | 'overlap';
  text_fr: string;
  correlations: { ticker: string; weight: number; correlation: number; evidence_id: string }[];
  corr_to_portfolio: number | null;
  asset_class_before: Record<string, number>;
  asset_class_after: Record<string, number>;
  currency_before: Record<string, number>;
  currency_after: Record<string, number>;
  n_asset_classes_before: number;
  n_asset_classes_after: number;
  evidence_ids: string[];
};

export type InstrumentProfile = {
  ticker: string;
  name: string;
  asset_class: AssetClass;
  label_fr: string;
  what_you_own_fr: string;
  return_source_fr: string;
  price_currency: 'CAD' | 'USD';
  risks: { risk: string; label_fr: string; question_fr: string; level: 'low' | 'medium' | 'high'; text_fr: string }[];
  source: string;
};

export type GovernanceControl = {
  id: string;
  label_fr: string;
  status: 'ok' | 'warning' | 'fail' | 'info';
  detail_fr: string;
  evidence_ids: string[];
};

export type Governance = { status: 'ok' | 'warning' | 'fail'; controls: GovernanceControl[]; missing_info: string[] };

export type WhatWouldChange = {
  rule_id: string | null;
  kind: 'weight' | 'profile';
  text_fr: string;
  max_weight: number | null;
  evidence_id: string;
};

export type WeightGridPoint = { weight: number; verdict: Verdict; rule_ids: string[] };

// v0.4.0 : contrôle de qualité des données et actifs téléchargés à la demande
export type QualityReport = {
  ticker: string;
  status: 'ok' | 'warning' | 'blocking';
  origin: 'starter_dataset' | 'on_demand';
  source: string;
  retrieved_at: string | null;
  first_date: string | null;
  last_date: string | null;
  n_obs: number;
  years: number;
  missing_days: number;
  missing_share: number;
  stale_runs: Record<string, unknown>[];
  outliers: Record<string, unknown>[];
  ohlc_issues: number;
  zero_volume_days: number;
  fx_filled_days: number;
  odd_splits: Record<string, unknown>[];
  warnings_fr: string[];
  notes_fr: string[];
  reference_calendar: string | null;
  evidence_id: string;
};

export type AssetSearchResult = {
  ticker: string;
  name: string;
  exchange: string;
  quote_type: string;
  supported: boolean;
  in_starter_dataset: boolean;
};

export type CoherenceResult = {
  verdict: Verdict;
  rule_hits: RuleHit[];
  metrics: {
    annualized_vol: number;
    max_drawdown: number;
    worst_calendar_year_return: number;
    position_weight_after: number;
  };
  explanation: Explanation;
  agent_trace?: ToolCall[] | null;
  diversification?: DiversificationImpact | null;
  instrument_risks?: InstrumentProfile | null;
  governance?: Governance | null;
  what_would_change?: WhatWouldChange[] | null;
  weight_grid?: WeightGridPoint[] | null;
  data_quality?: QualityReport | null;
  asset_origin?: 'starter_dataset' | 'on_demand' | null;
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
  // v0.3.0 : ciblage des nouvelles (optionnel)
  source_tier?: { id: 'primary' | 'established' | 'aggregator' | 'unknown'; label_fr: string; text_fr: string } | null;
  cluster?: { size: number; sources: string[]; news_ids: string[] } | null;
  mention?: 'title' | 'snippet' | 'none' | 'not_applicable' | null;
  linked_ticker?: string | null;
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
  data_quality?: QualityReport[] | null;
};

// v0.3.0 : note libre -> préférences à confirmer
export type ConfirmedPreferences = { excluded_sectors?: string[]; interests?: string[]; avoid_controversies?: boolean | null };
export type PreferenceSuggestion = {
  field: 'excluded_sectors' | 'interests' | 'avoid_controversies';
  value: string | boolean;
  label_fr: string;
  quote: string;
};
export type PreferenceExtraction = {
  note: string;
  suggestions: PreferenceSuggestion[];
  rejected: string[];
  generated_by: 'bedrock' | 'keywords';
  mentions_profile_change: boolean;
  notice_fr: string;
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
export type Question = { id: string; text: string; help?: string; optional?: boolean; options: QuestionOption[] };
export type Questionnaire = { version: number; questions: Question[] };

// rules/glossary.yaml
export type GlossaryTerm = { id: string; term: string; definition_fr: string };
export type Glossary = { terms: GlossaryTerm[] };
