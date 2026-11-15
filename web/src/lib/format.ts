// Formatage uniquement : le front ne calcule aucun chiffre financier.

const pctFmt = (digits: number) =>
  new Intl.NumberFormat('fr-CA', { style: 'percent', minimumFractionDigits: digits, maximumFractionDigits: digits });

/** Fraction (0,123) -> « 12,3 % ». */
export function formatPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return pctFmt(digits).format(value);
}

/** Fraction signée -> « +12,3 % » / « −4,0 % ». */
export function formatSignedPct(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  const s = formatPct(Math.abs(value), digits);
  if (value > 0) return `+${s}`;
  if (value < 0) return `−${s}`;
  return s;
}

const cadFmt = new Intl.NumberFormat('fr-CA', { style: 'currency', currency: 'CAD', maximumFractionDigits: 0 });
export function formatCad(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return cadFmt.format(value);
}

const dateFmt = new Intl.DateTimeFormat('fr-CA', { year: 'numeric', month: 'long', day: 'numeric', timeZone: 'UTC' });
/** « 2022-07-13 » ou ISO 8601 -> « 13 juillet 2022 ». */
export function formatDate(iso: string): string {
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
  if (Number.isNaN(d.getTime())) return iso;
  return dateFmt.format(d);
}

const numFmt = new Intl.NumberFormat('fr-CA', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
/** Nombre sans unité (ex. corrélation) -> « 0,91 ». */
export function formatNum(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—';
  return numFmt.format(value).replace('-', '−');
}

/** Valeur d'une preuve, selon son unité. */
export function formatEvidenceValue(value: number | string | null, unit: string | null): string {
  if (value === null) return '—';
  if (typeof value === 'string') return value;
  switch (unit) {
    case 'fraction':
    case 'pct':
      return formatPct(value);
    case 'CAD':
      return formatCad(value);
    case 'days':
      return `${value} jours`;
    default:
      return unit ? `${value} ${unit}` : String(value);
  }
}
