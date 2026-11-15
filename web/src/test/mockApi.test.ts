import { buildFeedMock, mockApi } from '../api/mock/mockApi';
import { MOCK_PERSONAS } from '../api/mock/personas';

async function feedFor(id: string, consideration?: { ticker: string; intended_weight: number }) {
  const persona = MOCK_PERSONAS.find((p) => p.id === id)!;
  const portfolio = await mockApi.parsePortfolio(persona.sample_portfolio_csv);
  return buildFeedMock(persona.profile, portfolio, consideration);
}

describe('mode simulé', () => {
  it('Robert et Amira obtiennent deux fils différents', async () => {
    const shownIds = async (id: string) => (await feedFor(id)).items.filter((i) => i.relevance.shown).map((i) => i.news_id);
    const robert = await shownIds('robert');
    const amira = await shownIds('amira');
    expect(robert).not.toEqual(amira);
    expect(robert).toContain('n04'); // dividende Fortis
    expect(amira).toContain('n05'); // réglementation crypto
  });

  it('une nouvelle sur un titre non détenu est masquée avec sa raison', async () => {
    const feed = await feedFor('robert');
    const tsla = feed.items.find((i) => i.news_id === 'n08')!;
    expect(tsla.relevance.shown).toBe(false);
    expect(tsla.explanation.summary).toMatch(/pas dans ton portefeuille/);
    expect(feed.hidden.count).toBe(feed.items.filter((i) => !i.relevance.shown).length);
  });

  it('chaque preuve citée existe dans le registre', async () => {
    const feed = await feedFor('mateo', { ticker: 'SPY', intended_weight: 0.1 });
    const claims = [...feed.items.flatMap((i) => i.explanation.claims), ...(feed.coherence?.explanation.claims ?? [])];
    for (const c of claims) for (const id of c.evidence_ids) expect(feed.evidence[id]).toBeDefined();
  });

  it('Robert avec 20 % de NVDA est incohérent, Amira en tension', async () => {
    expect((await feedFor('robert', { ticker: 'NVDA', intended_weight: 0.2 })).coherence?.verdict).toBe('incoherent');
    expect((await feedFor('amira', { ticker: 'NVDA', intended_weight: 0.2 })).coherence?.verdict).toBe('tension');
  });

  it('refuse un CSV sans en-tête valide', async () => {
    await expect(mockApi.parsePortfolio('foo,bar\nX,1')).rejects.toMatchObject({ code: 'INVALID_CSV' });
  });

  it('signale les titres hors univers et les doublons', async () => {
    const p = await mockApi.parsePortfolio('ticker,montant\nRY.TO,100\nRY.TO,100\nZZZ,200\n');
    expect(p.unanalyzed.tickers).toEqual(['ZZZ']);
    expect(p.unanalyzed.weight).toBeCloseTo(0.5);
    expect(p.warnings.join(' ')).toMatch(/deux fois/);
  });
});
