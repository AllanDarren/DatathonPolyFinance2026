import { formatEvidenceValue, formatPct, formatSignedPct } from '../lib/format';

const norm = (s: string) => s.replace(/\s/g, ' ');

describe('format', () => {
  it('formate une fraction en pourcentage', () => {
    expect(norm(formatPct(0.123))).toBe('12,3 %');
    expect(formatPct(null)).toBe('—');
  });
  it('signe les pourcentages', () => {
    expect(norm(formatSignedPct(-0.5, 0))).toBe('−50 %');
    expect(norm(formatSignedPct(0.031))).toBe('+3,1 %');
  });
  it('formate une preuve selon son unité', () => {
    expect(norm(formatEvidenceValue(0.4, 'fraction'))).toBe('40,0 %');
    expect(formatEvidenceValue('earnings_results', null)).toBe('earnings_results');
  });
});
