// Faux backend pour le mode simulé (VITE_MOCK=1).
// Il imite grossièrement services/ (rôle A) pour monter l'interface sans API.
// Les calculs ici NE sont PAS ceux du produit : en mode réel, tout vient de l'API.
import questionnaireJson from '../../generated/questionnaire.json';
import type {
  CoherenceResult, ConfirmedPreferences, Consideration, Event, Evidence, FeedItem, FeedResponse, Portfolio, Position,
  PreferenceExtraction, PreferenceSuggestion, Profile, Questionnaire, RelevanceLevel, RiskTolerance, RuleHit, Claim,
} from '../../types/contracts';
import { UNIVERSE_BY_TICKER } from '../../lib/universe';
import { formatPct } from '../../lib/format';
import { t } from '../../strings';
import type { Api } from '../client';
import { ApiRequestError } from '../errors';
import { MOCK_NEWS, type MockNews } from './news';
import { MOCK_CUSTOM_PROFILE, MOCK_PERSONAS } from './personas';

const DATA_AS_OF = '2026-11-12';
const NEWS_AS_OF = '2026-11-13';
const MOCK_SOURCE = 'mode simulé (web/src/api/mock)';

const delay = <T>(value: T, ms = 250): Promise<T> =>
  new Promise((resolve) => setTimeout(() => resolve(structuredClone(value)), ms));

// ---------- Profil ----------

const LIMITS: Record<RiskTolerance, Profile['limits']> = {
  low: { max_single_position: 0.08, max_high_vol_share: 0.05 },
  low_moderate: { max_single_position: 0.1, max_high_vol_share: 0.1 },
  moderate: { max_single_position: 0.15, max_high_vol_share: 0.25 },
  high: { max_single_position: 0.25, max_high_vol_share: 0.6 },
};

function scoreProfileMock(answers: Record<string, string>): Profile {
  const q = questionnaireJson as Questionnaire;
  const profile: Profile = structuredClone(MOCK_CUSTOM_PROFILE);
  let risk = 0;
  for (const question of q.questions) {
    const opt = question.options.find((o) => o.id === answers[question.id]);
    if (!opt) continue;
    risk += opt.points?.risk ?? 0;
    for (const [k, v] of Object.entries(opt.sets ?? {})) {
      (profile as unknown as Record<string, unknown>)[k] = v;
    }
  }
  profile.risk_tolerance = risk <= 3 ? 'low' : risk <= 6 ? 'low_moderate' : risk <= 9 ? 'moderate' : 'high';
  profile.horizon_bucket = profile.horizon_years <= 5 ? 'short' : profile.horizon_years <= 12 ? 'medium' : 'long';
  profile.limits = LIMITS[profile.risk_tolerance];
  profile.inconsistencies = [];
  if (profile.risk_tolerance === 'high' && profile.horizon_years <= 3) {
    profile.inconsistencies.push('Tolérance au risque élevée, mais horizon court.');
  }
  return profile;
}

// ---------- Portefeuille ----------

function parsePortfolioMock(csv: string): Portfolio {
  const lines = csv.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  const header = lines.shift()?.toLowerCase().replace(/\s/g, '');
  if (!header || !/^ticker[,;](montant|amount)$/.test(header)) {
    throw new ApiRequestError('INVALID_CSV', 'En-tête attendu : ticker,montant', 400);
  }
  const warnings: string[] = [];
  const amounts = new Map<string, number>();
  for (const [i, line] of lines.entries()) {
    const [rawTicker, rawAmount] = line.split(/[,;]/);
    const ticker = (rawTicker ?? '').trim().toUpperCase();
    const amount = Number((rawAmount ?? '').replace(/\s/g, ''));
    if (!ticker || !Number.isFinite(amount) || amount <= 0) {
      warnings.push(`Ligne ${i + 2} ignorée : montant invalide.`);
      continue;
    }
    if (amounts.has(ticker)) warnings.push(`${ticker} apparaît deux fois : montants additionnés.`);
    amounts.set(ticker, (amounts.get(ticker) ?? 0) + amount);
  }
  if (amounts.size === 0) throw new ApiRequestError('INVALID_CSV', 'Aucune ligne valide.', 400);

  const inUni = [...amounts].filter(([tk]) => UNIVERSE_BY_TICKER[tk]);
  const outUni = [...amounts].filter(([tk]) => !UNIVERSE_BY_TICKER[tk]);
  const totalAll = [...amounts.values()].reduce((a, b) => a + b, 0);
  const total = inUni.reduce((a, [, v]) => a + v, 0);
  const positions: Position[] = inUni
    .map(([ticker, amount]) => {
      const asset = UNIVERSE_BY_TICKER[ticker]!;
      return {
        ticker, amount, weight: total ? amount / total : 0,
        asset_class: asset.asset_class, price_currency: asset.currency, in_universe: true,
      };
    })
    .sort((a, b) => b.amount - a.amount);
  if (outUni.length) warnings.push(`Titres hors univers, non analysés : ${outUni.map(([tk]) => tk).join(', ')}.`);
  return {
    base_currency: 'CAD',
    total_amount: total,
    positions,
    unanalyzed: { tickers: outUni.map(([tk]) => tk), weight: totalAll ? (totalAll - total) / totalAll : 0 },
    warnings,
  };
}

// ---------- Fil ----------

const BASE_WEIGHTS: Record<Profile['horizon_bucket'], Record<string, number>> = {
  short: { earnings_results: 0.6, dividend: 0.8, rate_decision: 0.8, inflation: 0.6, regulation: 0.3, controversy: 0.3, rumor_hype: 0.05 },
  medium: { earnings_results: 0.55, dividend: 0.5, rate_decision: 0.5, inflation: 0.45, regulation: 0.4, controversy: 0.35, rumor_hype: 0.05 },
  long: { earnings_results: 0.5, dividend: 0.3, rate_decision: 0.3, inflation: 0.25, regulation: 0.5, controversy: 0.3, rumor_hype: 0.05 },
};
const SHOW = 0.35;
const HIGH = 0.7;
const HIGH_VOL = new Set(['NVDA', 'TSLA', 'SHOP.TO', 'BTC-USD', 'ETH-USD']);

const REASON_NOT_HELD = 'Ce titre n’est pas dans ton portefeuille.';
const REASON_NOISE = 'Bruit à court terme pour ton horizon.';
const REASON_LOW = 'Pertinence sous le seuil d’affichage pour ton profil.';

class EvidenceBook {
  private n = 0;
  readonly all: Record<string, Evidence> = {};
  add(e: Omit<Evidence, 'id' | 'as_of' | 'source'> & { source?: string }): string {
    this.n += 1;
    const id = `ev_${String(this.n).padStart(3, '0')}`;
    this.all[id] = { as_of: DATA_AS_OF, source: MOCK_SOURCE, ...e, id };
    return id;
  }
}

function scoreNews(news: MockNews, profile: Profile, portfolio: Portfolio, book: EvidenceBook): FeedItem {
  const held = portfolio.positions.filter((p) => news.tickers.includes(p.ticker));
  const weight = held.reduce((a, p) => a + p.weight, 0);
  const bucket = profile.horizon_bucket;
  const base = BASE_WEIGHTS[bucket][news.category] ?? 0.3;
  const hits: RuleHit[] = [];
  const claims: Claim[] = [];
  let hiddenReason: string | null = null;

  const evNews = book.add({
    kind: 'news_source', statement: `Titre publié par ${news.source} le ${news.published_at.slice(0, 10)}.`,
    value: news.url, unit: null, inputs: { news_id: news.id }, source: news.url, computed_by: 'ingest.snapshot (simulé)',
  });
  const evClass = book.add({
    kind: 'classification', statement: `Catégorie : ${t.labels.categories[news.category] ?? news.category}.`,
    value: news.category, unit: null, inputs: { title: news.title }, computed_by: 'agents.classifier (simulé)',
  });

  let score: number;
  if (news.scope === 'ticker' && weight === 0) {
    score = 0;
    hiddenReason = REASON_NOT_HELD;
    hits.push({ rule_id: 'R_NOT_HELD', text: REASON_NOT_HELD, severity: 'low' });
  } else {
    score = news.scope === 'macro' && weight === 0 ? base * 0.5 : base;
    hits.push({
      rule_id: 'R_BASE',
      text: `Catégorie ${t.labels.categories[news.category] ?? news.category} : pertinence ${base.toFixed(2)} pour un horizon ${t.labels.horizonBucket[bucket]}.`,
      delta: base,
    });
    const bonus = weight >= 0.2 ? 0.2 : weight >= 0.1 ? 0.1 : 0;
    if (bonus) {
      score += bonus;
      hits.push({ rule_id: 'R_POSITION_WEIGHT', text: `Position importante dans ton portefeuille (${formatPct(weight)}).`, delta: bonus, observed: weight });
    }
    if (profile.preferences.avoid_controversies && news.controversy) {
      score += 0.4;
      hits.push({ rule_id: 'R_PREF_CONTROVERSY', text: 'Controverse liée à un titre que tu détiens, et tu as dit vouloir les éviter.', delta: 0.4, severity: 'high' });
    }
    if (news.themes.some((th) => profile.preferences.interests.includes(th))) {
      score += 0.2;
      hits.push({ rule_id: 'R_INTEREST', text: 'Sujet qui fait partie de tes intérêts déclarés.', delta: 0.2 });
    }
    if (news.horizon_relevance === 'short_term_noise') {
      hits.push({ rule_id: 'R_NOISE', text: REASON_NOISE, severity: 'low' });
      hiddenReason = REASON_NOISE;
    }
  }
  score = Math.min(1, Math.round(score * 100) / 100);
  const shown = score >= SHOW && hiddenReason !== REASON_NOISE;
  if (!shown && !hiddenReason) hiddenReason = REASON_LOW;
  const level: RelevanceLevel = score >= HIGH ? 'high' : score >= SHOW ? 'medium' : 'low';

  if (held.length) {
    const evW = book.add({
      kind: 'portfolio_calc', statement: `Poids de ${held.map((p) => p.ticker).join(' + ')} dans le portefeuille.`,
      value: weight, unit: 'fraction', inputs: { tickers: held.map((p) => p.ticker) }, computed_by: 'core.portfolio.position_weight (simulé)',
    });
    claims.push({ text: `Tu détiens ${held.map((p) => p.ticker).join(' et ')} : ${formatPct(weight)} de ton portefeuille.`, label: 'fact', evidence_ids: [evW], verified: 'supported' });
  }
  claims.push({
    text: `Cette nouvelle est classée « ${t.labels.categories[news.category] ?? news.category} » (${t.horizonRelevance[news.horizon_relevance].toLowerCase()}).`,
    label: 'fact', evidence_ids: [evClass, evNews], verified: 'supported',
  });
  for (const h of hits) {
    const evR = book.add({ kind: 'rule_hit', statement: h.text, value: h.delta ?? null, unit: null, inputs: { rule_id: h.rule_id }, source: 'rules/relevance_rules.yaml', computed_by: 'core.rules.apply (simulé)' });
    claims.push({ text: h.text, label: 'fact', evidence_ids: [evR], verified: 'supported' });
  }
  if (news.category === 'rumor_hype') {
    claims.push({ text: 'Aucune source primaire ne confirme cette information à ce stade.', label: 'hypothesis', evidence_ids: [], verified: 'not_checked' });
  }

  let historical_context: FeedItem['historical_context'] = null;
  if (news.history && held.some((p) => p.ticker === news.history!.asset)) {
    const evH = book.add({
      kind: 'event_study', statement: `Médiane des mouvements de ${news.history.asset} sur ${news.history.n_events} événements comparables.`,
      value: news.history.median_return, unit: 'fraction', inputs: { window: news.history.window, n_events: news.history.n_events },
      computed_by: 'core.event_study.distribution (simulé)',
    });
    historical_context = { ...news.history, evidence_id: evH };
    claims.push({
      text: `Dans ${news.history.n_events} situations comparables, le mouvement médian de ${news.history.asset} a été de ${formatPct(news.history.median_return)}. Ce n’est pas une prévision.`,
      label: 'fact', evidence_ids: [evH], verified: 'supported',
    });
  }

  const summary = shown
    ? `Pertinence ${t.levels[level].toLowerCase()} pour ton profil : ${hits.map((h) => h.text.replace(/\.$/, '').toLowerCase()).slice(-1)[0] ?? ''}.`
    : hiddenReason ?? REASON_LOW;

  return {
    news_id: news.id, title: news.title, url: news.url, source: news.source, published_at: news.published_at,
    tickers: news.tickers, is_synthetic: true, category: news.category, horizon_relevance: news.horizon_relevance,
    relevance: { score, level, shown, position_weight: weight, rule_hits: hits },
    explanation: { summary, claims, generated_by: 'template', guardian: { status: 'passed', flags: [] } },
    historical_context,
  };
}

// ---------- Cohérence ----------

// Valeurs d'exploration du contexte commun (section 6), à revalider : mode simulé seulement.
const MOCK_METRICS: Record<string, { annualized_vol: number; max_drawdown: number; worst_calendar_year_return: number }> = {
  NVDA: { annualized_vol: 0.5, max_drawdown: -0.66, worst_calendar_year_return: -0.5 },
  'BTC-USD': { annualized_vol: 0.54, max_drawdown: -0.76, worst_calendar_year_return: -0.64 },
  SPY: { annualized_vol: 0.15, max_drawdown: -0.245, worst_calendar_year_return: -0.182 },
};

function coherenceMock(profile: Profile, portfolio: Portfolio, c: Consideration, book: EvidenceBook): CoherenceResult {
  const m = MOCK_METRICS[c.ticker];
  if (!m) {
    throw new ApiRequestError('MOCK_UNAVAILABLE', `En mode simulé, seuls ${Object.keys(MOCK_METRICS).join(', ')} sont disponibles.`, 400);
  }
  const hits: RuleHit[] = [];
  const claims: Claim[] = [];
  const evVol = book.add({ kind: 'metric', statement: `Volatilité annualisée de ${c.ticker}.`, value: m.annualized_vol, unit: 'fraction', inputs: { ticker: c.ticker, window: '5 ans' }, computed_by: 'core.metrics.annualized_vol (simulé)' });
  const evMdd = book.add({ kind: 'metric', statement: `Pire chute historique de ${c.ticker}.`, value: m.max_drawdown, unit: 'fraction', inputs: { ticker: c.ticker }, computed_by: 'core.metrics.max_drawdown (simulé)' });
  const evW = book.add({ kind: 'portfolio_calc', statement: 'Poids visé après ajout.', value: c.intended_weight, unit: 'fraction', inputs: { ...c }, computed_by: 'core.portfolio.position_weight_after (simulé)' });

  if (c.intended_weight > profile.limits.max_single_position) {
    hits.push({ rule_id: 'C_MAX_SINGLE', severity: 'high', observed: c.intended_weight, limit: profile.limits.max_single_position,
      text: `Cette position dépasserait la limite de ${formatPct(profile.limits.max_single_position, 0)} par titre prévue pour ton profil (valeur : ${formatPct(c.intended_weight, 0)}).` });
    claims.push({ text: `Avec ${formatPct(c.intended_weight, 0)} du portefeuille, ${c.ticker} dépasserait la limite de ${formatPct(profile.limits.max_single_position, 0)} par titre de ton profil.`, label: 'fact', evidence_ids: [evW], verified: 'supported' });
  }
  if (Math.abs(m.max_drawdown) > profile.max_acceptable_loss_pct) {
    hits.push({ rule_id: 'C_DRAWDOWN_VS_LOSS', severity: 'medium', observed: Math.abs(m.max_drawdown), limit: profile.max_acceptable_loss_pct,
      text: 'La pire chute historique de ce titre dépasse la perte que tu dis pouvoir accepter.' });
    claims.push({ text: `La pire chute historique de ${c.ticker} a été de ${formatPct(m.max_drawdown, 0)}, alors que tu dis pouvoir accepter ${formatPct(profile.max_acceptable_loss_pct, 0)}.`, label: 'fact', evidence_ids: [evMdd], verified: 'supported' });
  }
  if (m.annualized_vol > 0.3) {
    const current = portfolio.positions.filter((p) => HIGH_VOL.has(p.ticker) && p.ticker !== c.ticker).reduce((a, p) => a + p.weight, 0);
    const after = current + c.intended_weight;
    if (after > profile.limits.max_high_vol_share) {
      hits.push({ rule_id: 'C_HIGH_VOL_SHARE', severity: 'medium', observed: after, limit: profile.limits.max_high_vol_share,
        text: 'La part de titres très volatils dépasserait la limite de ton profil.' });
      claims.push({ text: `${c.ticker} est très volatil (${formatPct(m.annualized_vol, 0)} par an) : la part de titres très volatils passerait à ${formatPct(after, 0)}.`, label: 'fact', evidence_ids: [evVol], verified: 'supported' });
    }
  }
  claims.push({ text: 'Si un épisode comme 2022 se reproduisait, la baisse pourrait être du même ordre, sans que rien ne le garantisse.', label: 'scenario', evidence_ids: [], verified: 'not_checked' });

  const verdict = hits.some((h) => h.severity === 'high') ? 'incoherent' : hits.some((h) => h.severity === 'medium') ? 'tension' : 'coherent';
  return {
    verdict,
    rule_hits: hits,
    metrics: { ...m, position_weight_after: c.intended_weight },
    explanation: {
      summary: `${t.consider.verdicts[verdict]} : ${hits.length} règle(s) en cause.`,
      claims, generated_by: 'template', guardian: { status: 'passed', flags: [] },
    },
    // v0.3.0 (imitation) : trace des agents et contrôles de gouvernance
    agent_trace: ['check_coherence', 'get_position_metrics', 'get_diversification_impact', 'get_instrument_risks',
      'what_would_change', 'governance_review', 'explain_and_guard'].map((tool, i) => ({
      step: i + 1, tool, params: i < 4 ? { ticker: c.ticker } : {}, evidence_ids: i === 0 ? [evW] : i === 1 ? [evVol, evMdd] : [],
      status: 'ok' as const, forced: false, planner: i < 4 ? 'mock' : 'code', duration_ms: 0,
    })),
    governance: {
      status: verdict === 'incoherent' ? 'fail' : verdict === 'tension' ? 'warning' : 'ok',
      controls: [
        { id: 'G_SIMULATION', label_fr: 'Simulation seulement', status: 'info', detail_fr: 'Aucune transaction; pas un conseil.', evidence_ids: [] },
        { id: 'G_PROFILE_LIMITS', label_fr: 'Limites de ton profil', status: verdict === 'incoherent' ? 'fail' : verdict === 'tension' ? 'warning' : 'ok',
          detail_fr: hits.length ? `Règle(s) : ${hits.map((h) => h.rule_id).join(', ')}.` : 'Aucune règle déclenchée.', evidence_ids: [] },
      ],
      missing_info: profile.monthly_expenses_cad ? [] : ['Dépenses mensuelles inconnues.'],
    },
  };
}

// ---------- Événements ----------

const MOCK_EVENTS: Event[] = [
  { id: 'e1', type: 'cpi_release', scope: 'macro', tickers: [], date: '2026-11-17', title: 'Publication de l’IPC canadien', is_estimated: false, source: 'Exemple fictif — calendrier officiel', retrieved_at: NEWS_AS_OF },
  { id: 'e2', type: 'earnings', scope: 'ticker', tickers: ['NVDA'], date: '2026-11-18', title: 'Résultats trimestriels de NVIDIA', is_estimated: true, source: 'Cadence trimestrielle observée (simulé)', retrieved_at: NEWS_AS_OF },
  { id: 'e3', type: 'dividend_ex_date', scope: 'ticker', tickers: ['FTS.TO'], date: '2026-11-18', title: 'Date ex-dividende de Fortis', is_estimated: true, source: 'corporate_actions.csv, cadence observée (simulé)', retrieved_at: NEWS_AS_OF },
  { id: 'e4', type: 'dividend_ex_date', scope: 'ticker', tickers: ['JNJ'], date: '2026-11-24', title: 'Date ex-dividende de Johnson & Johnson', is_estimated: true, source: 'corporate_actions.csv, cadence observée (simulé)', retrieved_at: NEWS_AS_OF },
  { id: 'e5', type: 'earnings', scope: 'ticker', tickers: ['RY.TO'], date: '2026-12-03', title: 'Résultats annuels de la Banque Royale', is_estimated: false, source: 'Exemple fictif — communiqué de société', retrieved_at: NEWS_AS_OF },
  { id: 'e6', type: 'rate_decision', scope: 'macro', tickers: [], date: '2026-12-09', title: 'Décision de taux de la Banque du Canada', is_estimated: false, source: 'Exemple fictif — calendrier officiel', retrieved_at: NEWS_AS_OF },
  { id: 'e7', type: 'earnings', scope: 'ticker', tickers: ['SHOP.TO'], date: '2027-02-11', title: 'Résultats trimestriels de Shopify', is_estimated: true, source: 'Cadence trimestrielle observée (simulé)', retrieved_at: NEWS_AS_OF },
];

function eventsFor(tickers?: string[]): Event[] {
  if (!tickers || tickers.length === 0) return MOCK_EVENTS;
  return MOCK_EVENTS.filter((e) => e.scope === 'macro' || e.tickers.some((tk) => tickers.includes(tk)));
}

// ---------- Fil complet ----------

export function buildFeedMock(profile: Profile, portfolio: Portfolio, consideration?: Consideration | null): FeedResponse {
  const book = new EvidenceBook();
  const items = MOCK_NEWS.map((n) => scoreNews(n, profile, portfolio, book)).sort((a, b) => b.relevance.score - a.relevance.score);
  const hiddenItems = items.filter((i) => !i.relevance.shown);
  const byReason = new Map<string, number>();
  for (const i of hiddenItems) {
    const r = i.explanation.summary;
    byReason.set(r, (byReason.get(r) ?? 0) + 1);
  }
  const classWeights: Record<string, number> = {};
  for (const p of portfolio.positions) classWeights[p.asset_class] = (classWeights[p.asset_class] ?? 0) + p.weight;
  const sorted = [...portfolio.positions].sort((a, b) => b.weight - a.weight);

  return {
    generated_at: new Date().toISOString(),
    data_as_of: DATA_AS_OF,
    news_as_of: NEWS_AS_OF,
    profile,
    portfolio_summary: {
      top_positions: sorted.slice(0, 5),
      asset_class_weights: classWeights,
      high_vol_share: portfolio.positions.filter((p) => HIGH_VOL.has(p.ticker)).reduce((a, p) => a + p.weight, 0),
      top3_concentration: sorted.slice(0, 3).reduce((a, p) => a + p.weight, 0),
    },
    items,
    hidden: { count: hiddenItems.length, by_reason: [...byReason].map(([reason, count]) => ({ reason, count })) },
    coherence: consideration ? coherenceMock(profile, portfolio, consideration, book) : null,
    events: eventsFor(portfolio.positions.map((p) => p.ticker)),
    evidence: book.all,
    disclaimers: [
      t.disclaimer,
      'Mode simulé : les nouvelles affichées sont des exemples fictifs.',
      'Aucune transaction, aucune recommandation d’achat ou de vente.',
    ],
    limits: [
      'Les données couvrent une seule fenêtre de 5 ans (nov. 2021 à nov. 2026), marquée par la hausse des taux.',
      'Biais du survivant : les 31 actifs ont été choisis en 2026.',
      'Le contexte historique décrit le passé ; il ne prédit pas l’avenir.',
      'Les montants sont en dollars canadiens ; les titres en USD sont convertis au taux de la Banque du Canada.',
      'Le classement des nouvelles par IA peut se tromper : chaque classement affiche son niveau de confiance.',
    ],
  };
}

// ---------- Note libre (imitation grossière de agents/preferences.py) ----------

const NOTE_RULES: { field: PreferenceSuggestion['field']; value: string | boolean; label_fr: string; re: RegExp }[] = [
  { field: 'excluded_sectors', value: 'fossil_fuels', label_fr: 'Exclure le secteur : Combustibles fossiles', re: /p[ée]trol\w*|fossile\w*|charbon|pipeline\w*/i },
  { field: 'excluded_sectors', value: 'tobacco', label_fr: 'Exclure le secteur : Tabac', re: /tabac\w*/i },
  { field: 'interests', value: 'ai', label_fr: 'Intérêt : intelligence artificielle', re: /\bIA\b|intelligence artificielle/i },
  { field: 'interests', value: 'crypto', label_fr: 'Intérêt : cryptoactifs', re: /crypto\w*|bitcoin/i },
  { field: 'interests', value: 'income', label_fr: 'Intérêt : revenus et dividendes', re: /dividende\w*/i },
  { field: 'avoid_controversies', value: true, label_fr: 'Faire ressortir les controverses (préférence ESG)', re: /controvers\w*|scandale\w*|[ée]thique\w*/i },
];

function extractPreferencesMock(text: string): PreferenceExtraction {
  const note = text.replace(/[<>]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 300);
  const suggestions: PreferenceSuggestion[] = [];
  for (const r of NOTE_RULES) {
    const m = note.match(r.re);
    if (m) suggestions.push({ field: r.field, value: r.value, label_fr: r.label_fr, quote: m[0] });
  }
  const change = /risque|horizon|retraite|perte/i.test(note);
  return {
    note,
    suggestions,
    rejected: [],
    generated_by: 'keywords',
    mentions_profile_change: change,
    notice_fr: 'Ces suggestions viennent de ta note. Rien n’est appliqué sans ta confirmation.'
      + (change ? ' Ta note semble parler de risque ou d’horizon : refais les questions concernées.' : ''),
  };
}

function applyConfirmedMock(profile: Profile, c?: ConfirmedPreferences | null): Profile {
  if (!c) return profile;
  const p = structuredClone(profile);
  p.preferences.excluded_sectors = [...new Set([...p.preferences.excluded_sectors, ...(c.excluded_sectors ?? [])])];
  p.preferences.interests = [...new Set([...p.preferences.interests, ...(c.interests ?? [])])];
  if (c.avoid_controversies) p.preferences.avoid_controversies = true;
  p.confirmed_from_note = [...(c.excluded_sectors ?? []), ...(c.interests ?? []), ...(c.avoid_controversies ? ['controverses'] : [])];
  return p;
}

export const mockApi: Api = {
  health: () => delay({ status: 'ok', version: 'mock', llm_provider: 'mock' }),
  getQuestionnaire: () => delay(questionnaireJson as Questionnaire),
  getPersonas: () => delay(MOCK_PERSONAS),
  scoreProfile: async (answers, confirmed) => delay(applyConfirmedMock(scoreProfileMock(answers), confirmed)),
  extractPreferences: async (text) => delay(extractPreferencesMock(text)),
  searchAssets: async (q) => delay(
    Object.values(UNIVERSE_BY_TICKER)
      .filter((a) => a.ticker.includes(q.toUpperCase()) || a.name.toLowerCase().includes(q.toLowerCase()))
      .slice(0, 8)
      .map((a) => ({ ticker: a.ticker, name: a.name, exchange: '', quote_type: 'STARTER', supported: true, in_starter_dataset: true })),
    100,
  ),
  parsePortfolio: async (csv) => delay(parsePortfolioMock(csv)),
  buildFeed: async (profile, portfolio, consideration) => delay(buildFeedMock(profile, portfolio, consideration), 500),
  getEvents: async (tickers) => delay(eventsFor(tickers)),
};
