// Les 31 actifs de assets_universe.csv (sert à l'autocomplétion uniquement).
import type { AssetClass } from '../types/contracts';

export type UniverseAsset = { ticker: string; name: string; asset_class: AssetClass; currency: 'CAD' | 'USD' };

export const UNIVERSE: UniverseAsset[] = [
  { ticker: 'RY.TO', name: 'Banque Royale du Canada', asset_class: 'equity_ca', currency: 'CAD' },
  { ticker: 'TD.TO', name: 'Banque TD', asset_class: 'equity_ca', currency: 'CAD' },
  { ticker: 'MFC.TO', name: 'Manuvie', asset_class: 'equity_ca', currency: 'CAD' },
  { ticker: 'ENB.TO', name: 'Enbridge', asset_class: 'equity_ca', currency: 'CAD' },
  { ticker: 'CNQ.TO', name: 'Canadian Natural Resources', asset_class: 'equity_ca', currency: 'CAD' },
  { ticker: 'CNR.TO', name: 'Canadien National', asset_class: 'equity_ca', currency: 'CAD' },
  { ticker: 'FTS.TO', name: 'Fortis', asset_class: 'equity_ca', currency: 'CAD' },
  { ticker: 'ATD.TO', name: 'Alimentation Couche-Tard', asset_class: 'equity_ca', currency: 'CAD' },
  { ticker: 'SHOP.TO', name: 'Shopify', asset_class: 'equity_ca', currency: 'CAD' },
  { ticker: 'CSU.TO', name: 'Constellation Software', asset_class: 'equity_ca', currency: 'CAD' },
  { ticker: 'AAPL', name: 'Apple', asset_class: 'equity_us', currency: 'USD' },
  { ticker: 'MSFT', name: 'Microsoft', asset_class: 'equity_us', currency: 'USD' },
  { ticker: 'NVDA', name: 'NVIDIA', asset_class: 'equity_us', currency: 'USD' },
  { ticker: 'GOOGL', name: 'Alphabet', asset_class: 'equity_us', currency: 'USD' },
  { ticker: 'AMZN', name: 'Amazon', asset_class: 'equity_us', currency: 'USD' },
  { ticker: 'TSLA', name: 'Tesla', asset_class: 'equity_us', currency: 'USD' },
  { ticker: 'JPM', name: 'JPMorgan Chase', asset_class: 'equity_us', currency: 'USD' },
  { ticker: 'JNJ', name: 'Johnson & Johnson', asset_class: 'equity_us', currency: 'USD' },
  { ticker: 'PG', name: 'Procter & Gamble', asset_class: 'equity_us', currency: 'USD' },
  { ticker: 'XOM', name: 'Exxon Mobil', asset_class: 'equity_us', currency: 'USD' },
  { ticker: 'XIU.TO', name: 'iShares S&P/TSX 60', asset_class: 'equity_etf', currency: 'CAD' },
  { ticker: 'SPY', name: 'SPDR S&P 500', asset_class: 'equity_etf', currency: 'USD' },
  { ticker: 'QQQ', name: 'Invesco QQQ (Nasdaq-100)', asset_class: 'equity_etf', currency: 'USD' },
  { ticker: 'ESGV', name: 'Vanguard ESG U.S. Stock', asset_class: 'equity_etf', currency: 'USD' },
  { ticker: 'XBB.TO', name: 'iShares obligations universelles canadiennes', asset_class: 'bond_etf', currency: 'CAD' },
  { ticker: 'ZST.TO', name: 'BMO obligations à très court terme', asset_class: 'bond_etf', currency: 'CAD' },
  { ticker: 'AGG', name: 'iShares Core U.S. Aggregate Bond', asset_class: 'bond_etf', currency: 'USD' },
  { ticker: 'TLT', name: 'iShares obligations du Trésor 20 ans et plus', asset_class: 'bond_etf', currency: 'USD' },
  { ticker: 'GLD', name: 'SPDR Gold Shares', asset_class: 'gold_etf', currency: 'USD' },
  { ticker: 'BTC-USD', name: 'Bitcoin', asset_class: 'crypto', currency: 'USD' },
  { ticker: 'ETH-USD', name: 'Ether', asset_class: 'crypto', currency: 'USD' },
];

export const UNIVERSE_BY_TICKER: Record<string, UniverseAsset> = Object.fromEntries(
  UNIVERSE.map((a) => [a.ticker, a]),
);
