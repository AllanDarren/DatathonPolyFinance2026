// Personas d'exemple pour le mode simulé. Remplacés par GET /personas (rules/personas/ du rôle D).
import type { Persona, Profile } from '../../types/contracts';

const base = { base_currency: 'CAD' as const, monthly_expenses_cad: null, source: 'persona_preset' as const };

const robert: Profile = {
  ...base,
  profile_id: 'robert',
  label: 'Robert',
  age: 59,
  horizon_years: 4,
  horizon_bucket: 'short',
  risk_tolerance: 'low_moderate',
  max_acceptable_loss_pct: 0.1,
  objective: 'capital_preservation',
  experience: 'intermediate',
  preferences: { avoid_controversies: false, excluded_sectors: [], interests: ['dividendes', 'taux'] },
  limits: { max_single_position: 0.1, max_high_vol_share: 0.1 },
  inconsistencies: [],
};

const amira: Profile = {
  ...base,
  profile_id: 'amira',
  label: 'Amira',
  age: 26,
  horizon_years: 20,
  horizon_bucket: 'long',
  risk_tolerance: 'high',
  max_acceptable_loss_pct: 0.35,
  objective: 'growth',
  experience: 'intermediate',
  preferences: { avoid_controversies: false, excluded_sectors: [], interests: ['ia', 'crypto'] },
  limits: { max_single_position: 0.25, max_high_vol_share: 0.6 },
  inconsistencies: [],
};

const mateo: Profile = {
  ...base,
  profile_id: 'mateo',
  label: 'Mateo',
  age: 41,
  horizon_years: 10,
  horizon_bucket: 'medium',
  risk_tolerance: 'moderate',
  max_acceptable_loss_pct: 0.2,
  objective: 'balanced',
  experience: 'intermediate',
  preferences: { avoid_controversies: true, excluded_sectors: ['Énergie fossile'], interests: ['esg'] },
  limits: { max_single_position: 0.15, max_high_vol_share: 0.25 },
  inconsistencies: [],
};

export const MOCK_PERSONAS: Persona[] = [
  {
    id: 'robert',
    label: 'Robert, 59 ans — proche de la retraite',
    profile: robert,
    sample_portfolio_csv:
      'ticker,montant\nXBB.TO,40000\nRY.TO,15000\nFTS.TO,12000\nENB.TO,10000\nZST.TO,10000\nXIU.TO,8000\nGLD,5000\n',
  },
  {
    id: 'amira',
    label: 'Amira, 26 ans — croissance, IA et cryptos',
    profile: amira,
    sample_portfolio_csv:
      'ticker,montant\nQQQ,12000\nNVDA,8000\nMSFT,6000\nXIU.TO,6000\nSHOP.TO,5000\nBTC-USD,5000\nAGG,5000\nETH-USD,3000\n',
  },
  {
    id: 'mateo',
    label: 'Mateo, 41 ans — équilibre et critères ESG',
    profile: mateo,
    sample_portfolio_csv:
      'ticker,montant\nESGV,28000\nXBB.TO,22000\nXIU.TO,16000\nAAPL,9000\nCNR.TO,9000\nJNJ,8000\nPG,8000\n',
  },
];

export const MOCK_CUSTOM_PROFILE: Profile = {
  ...mateo,
  profile_id: 'custom',
  label: 'Ton profil',
  source: 'questionnaire',
  age: undefined,
  preferences: { avoid_controversies: false, excluded_sectors: [], interests: [] },
};
