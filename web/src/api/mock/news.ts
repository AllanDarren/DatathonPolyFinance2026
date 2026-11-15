// Journée de nouvelles FICTIVES pour le mode simulé (is_synthetic: true partout).
// Aucun de ces titres n'est une vraie nouvelle : ils servent à monter l'interface.
import type { HistoricalContext, HorizonRelevance } from '../../types/contracts';

export type MockNews = {
  id: string;
  title: string;
  source: string;
  url: string;
  published_at: string;
  tickers: string[];
  scope: 'ticker' | 'macro';
  category: string;
  horizon_relevance: HorizonRelevance;
  controversy: boolean;
  themes: string[];
  history?: Omit<HistoricalContext, 'evidence_id'>;
};

const CAVEATS = [
  'Échantillon petit : peu de cas comparables sur 5 ans.',
  'Les fenêtres peuvent se chevaucher avec d’autres nouvelles.',
  'Biais du survivant : les 31 actifs ont été choisis en 2026.',
  'Ce qui s’est passé avant n’est pas une prévision.',
];

const url = (id: string) => `https://example.org/fictif/${id}`;

export const MOCK_NEWS: MockNews[] = [
  {
    id: 'n01',
    title: 'La Banque du Canada annonce sa décision sur le taux directeur',
    source: 'Exemple fictif — Banque centrale',
    url: url('n01'),
    published_at: '2026-11-12T14:45:00Z',
    tickers: ['XBB.TO', 'ZST.TO', 'AGG'],
    scope: 'macro',
    category: 'rate_decision',
    horizon_relevance: 'macro_context',
    controversy: false,
    themes: ['taux'],
    history: {
      event_type: 'rate_decision',
      asset: 'XBB.TO',
      window: 'veille à +5 jours de bourse',
      n_events: 12,
      median_return: -0.002,
      p10: -0.014,
      p90: 0.011,
      share_positive: 0.42,
      events: [
        { date: '2022-03-02', return: -0.009 },
        { date: '2022-06-01', return: -0.012 },
        { date: '2022-07-13', return: 0.008 },
        { date: '2022-09-07', return: -0.015 },
        { date: '2022-10-26', return: 0.011 },
        { date: '2023-01-25', return: 0.006 },
      ],
      caveats: CAVEATS,
    },
  },
  {
    id: 'n02',
    title: 'NVIDIA publie ses résultats du troisième trimestre',
    source: 'Exemple fictif — Communiqué de société',
    url: url('n02'),
    published_at: '2026-11-12T21:05:00Z',
    tickers: ['NVDA'],
    scope: 'ticker',
    category: 'earnings_results',
    horizon_relevance: 'structural',
    controversy: false,
    themes: ['ia'],
    history: {
      event_type: 'earnings',
      asset: 'NVDA',
      window: 'veille à +5 jours de bourse',
      n_events: 19,
      median_return: 0.031,
      p10: -0.087,
      p90: 0.162,
      share_positive: 0.63,
      events: [
        { date: '2023-05-24', return: 0.245 },
        { date: '2023-08-23', return: 0.012 },
        { date: '2024-02-21', return: 0.164 },
        { date: '2024-08-28', return: -0.091 },
        { date: '2025-02-26', return: -0.118 },
      ],
      caveats: CAVEATS,
    },
  },
  {
    id: 'n03',
    title: 'Rumeur : Microsoft envisagerait une grosse acquisition dans l’IA',
    source: 'Exemple fictif — Blogue financier',
    url: url('n03'),
    published_at: '2026-11-13T09:20:00Z',
    tickers: ['MSFT'],
    scope: 'ticker',
    category: 'rumor_hype',
    horizon_relevance: 'short_term_noise',
    controversy: false,
    themes: ['ia'],
  },
  {
    id: 'n04',
    title: 'Fortis déclare son dividende trimestriel',
    source: 'Exemple fictif — Communiqué de société',
    url: url('n04'),
    published_at: '2026-11-12T11:00:00Z',
    tickers: ['FTS.TO'],
    scope: 'ticker',
    category: 'dividend',
    horizon_relevance: 'structural',
    controversy: false,
    themes: ['dividendes'],
  },
  {
    id: 'n05',
    title: 'Projet d’encadrement des plateformes de cryptoactifs soumis à consultation',
    source: 'Exemple fictif — Autorité de réglementation',
    url: url('n05'),
    published_at: '2026-11-11T16:30:00Z',
    tickers: ['BTC-USD', 'ETH-USD'],
    scope: 'ticker',
    category: 'regulation',
    horizon_relevance: 'structural',
    controversy: false,
    themes: ['crypto'],
  },
  {
    id: 'n06',
    title: 'Johnson & Johnson : nouveau jugement dans les litiges sur le talc',
    source: 'Exemple fictif — Agence de presse',
    url: url('n06'),
    published_at: '2026-11-12T18:10:00Z',
    tickers: ['JNJ'],
    scope: 'ticker',
    category: 'controversy',
    horizon_relevance: 'structural',
    controversy: true,
    themes: ['esg'],
  },
  {
    id: 'n07',
    title: 'Statistique Canada publie l’indice des prix à la consommation',
    source: 'Exemple fictif — Agence statistique',
    url: url('n07'),
    published_at: '2026-11-13T13:30:00Z',
    tickers: ['XIU.TO', 'XBB.TO'],
    scope: 'macro',
    category: 'inflation',
    horizon_relevance: 'macro_context',
    controversy: false,
    themes: ['taux'],
  },
  {
    id: 'n08',
    title: 'Le titre de Tesla s’emballe après une publication sur les réseaux sociaux',
    source: 'Exemple fictif — Réseau social',
    url: url('n08'),
    published_at: '2026-11-13T15:00:00Z',
    tickers: ['TSLA'],
    scope: 'ticker',
    category: 'rumor_hype',
    horizon_relevance: 'short_term_noise',
    controversy: false,
    themes: [],
  },
  {
    id: 'n09',
    title: 'Enbridge : manifestation contre un projet de pipeline',
    source: 'Exemple fictif — Média régional',
    url: url('n09'),
    published_at: '2026-11-12T20:00:00Z',
    tickers: ['ENB.TO'],
    scope: 'ticker',
    category: 'controversy',
    horizon_relevance: 'structural',
    controversy: true,
    themes: ['esg'],
  },
  {
    id: 'n10',
    title: 'Banque Royale : date de publication des résultats annuels annoncée',
    source: 'Exemple fictif — Communiqué de société',
    url: url('n10'),
    published_at: '2026-11-10T12:00:00Z',
    tickers: ['RY.TO'],
    scope: 'ticker',
    category: 'earnings_results',
    horizon_relevance: 'structural',
    controversy: false,
    themes: ['dividendes'],
  },
];
