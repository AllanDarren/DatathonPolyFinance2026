// Convertit rules/glossary.yaml et rules/questionnaire.yaml (rôle D) en JSON pour le front.
// Si un fichier n'existe pas encore, on écrit un brouillon de secours marqué comme tel.
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import yaml from 'js-yaml';

const here = dirname(fileURLToPath(import.meta.url));
const rulesDir = resolve(here, '../../rules');
const outDir = resolve(here, '../src/generated');
mkdirSync(outDir, { recursive: true });

const FALLBACK = {
  glossary: {
    _fallback: true,
    terms: [
      { id: 'volatility', term: 'volatilité', definition_fr: 'Ampleur des variations habituelles d’un prix. Plus elle est élevée, plus le prix bouge fort, dans les deux sens.' },
      { id: 'max_drawdown', term: 'pire chute', definition_fr: 'Plus forte baisse entre un sommet et le creux qui a suivi, sur la période étudiée.' },
      { id: 'horizon', term: 'horizon', definition_fr: 'Nombre d’années avant d’avoir besoin d’une partie importante de cet argent.' },
      { id: 'etf', term: 'FNB', definition_fr: 'Fonds négocié en bourse : un panier de titres qui s’achète comme une action.' },
      { id: 'ex_dividend', term: 'date ex-dividende', definition_fr: 'Date à partir de laquelle un nouvel acheteur ne reçoit plus le prochain dividende.' },
      { id: 'concentration', term: 'concentration', definition_fr: 'Part du portefeuille placée dans quelques titres seulement.' },
    ],
  },
  questionnaire: {
    _fallback: true,
    version: 1,
    questions: [
      { id: 'q_horizon', text: 'Dans combien d’années auras-tu besoin d’une partie importante de cet argent?', help: 'Pense à la retraite, à un achat important ou à un projet.',
        options: [
          { id: 'h_lt3', label: 'Moins de 3 ans', sets: { horizon_years: 2 } },
          { id: 'h_3_5', label: '3 à 5 ans', sets: { horizon_years: 4 } },
          { id: 'h_6_12', label: '6 à 12 ans', sets: { horizon_years: 9 } },
          { id: 'h_gt15', label: 'Plus de 12 ans', sets: { horizon_years: 20 } },
        ] },
      { id: 'q_drop', text: 'Ton portefeuille perd 20 % en trois mois. Que fais-tu?',
        options: [
          { id: 'd_sell', label: 'Je vends pour limiter les dégâts', points: { risk: 0 }, sets: { max_acceptable_loss_pct: 0.08 } },
          { id: 'd_wait', label: 'J’attends, inquiet', points: { risk: 2 }, sets: { max_acceptable_loss_pct: 0.15 } },
          { id: 'd_hold', label: 'Je ne touche à rien', points: { risk: 3 }, sets: { max_acceptable_loss_pct: 0.25 } },
          { id: 'd_buy', label: 'J’en profite pour en racheter', points: { risk: 4 }, sets: { max_acceptable_loss_pct: 0.35 } },
        ] },
      { id: 'q_objective', text: 'Quel est ton objectif principal?',
        options: [
          { id: 'o_preserve', label: 'Protéger ce que j’ai', points: { risk: 0 }, sets: { objective: 'capital_preservation' } },
          { id: 'o_income', label: 'Un revenu régulier', points: { risk: 1 }, sets: { objective: 'income' } },
          { id: 'o_balanced', label: 'Un équilibre croissance et stabilité', points: { risk: 2 }, sets: { objective: 'balanced' } },
          { id: 'o_growth', label: 'Faire croître mon capital', points: { risk: 3 }, sets: { objective: 'growth' } },
        ] },
      { id: 'q_experience', text: 'Ton expérience en placement?',
        options: [
          { id: 'x_beginner', label: 'Je débute', points: { risk: 0 }, sets: { experience: 'beginner' } },
          { id: 'x_intermediate', label: 'J’ai déjà investi', points: { risk: 1 }, sets: { experience: 'intermediate' } },
          { id: 'x_advanced', label: 'Je suis à l’aise', points: { risk: 2 }, sets: { experience: 'advanced' } },
        ] },
      { id: 'q_controversy', text: 'Veux-tu être alerté des controverses (environnement, social, gouvernance) sur tes titres?',
        options: [
          { id: 'c_yes', label: 'Oui, je veux les éviter', sets: { preferences: { avoid_controversies: true, excluded_sectors: [], interests: ['esg'] } } },
          { id: 'c_no', label: 'Pas particulièrement', sets: { preferences: { avoid_controversies: false, excluded_sectors: [], interests: [] } } },
        ] },
      { id: 'q_emergency', text: 'As-tu une réserve d’urgence de quelques mois de dépenses?',
        options: [
          { id: 'e_no', label: 'Non', points: { risk: 0 } },
          { id: 'e_yes', label: 'Oui', points: { risk: 1 } },
        ] },
    ],
  },
};

for (const name of ['glossary', 'questionnaire']) {
  const src = resolve(rulesDir, `${name}.yaml`);
  let data;
  if (existsSync(src)) {
    data = yaml.load(readFileSync(src, 'utf8'));
    console.log(`build-data: ${name} <- rules/${name}.yaml`);
  } else {
    data = FALLBACK[name];
    console.log(`build-data: rules/${name}.yaml absent, brouillon de secours utilisé`);
  }
  writeFileSync(resolve(outDir, `${name}.json`), JSON.stringify(data, null, 2) + '\n');
}
