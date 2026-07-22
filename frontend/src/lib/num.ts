// Backend serializes Decimal fields; over JSON they may arrive as strings
// (e.g. "3.2000") or numbers. Normalize everything to a JS number for math
// and rendering, and format cleanly for display.

export function toNum(value: unknown): number | null {
  if (value === null || value === undefined || value === '') return null;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

// Trim trailing zeros from a decimal-ish value: 3.2000 -> "3.2", 5.0 -> "5".
export function fmtNum(value: unknown, fallback = '-'): string {
  const n = toNum(value);
  if (n === null) return fallback;
  return String(Number(n.toFixed(4)));
}

export function fmtPercent(progress: unknown): string {
  const n = toNum(progress);
  if (n === null) return '0%';
  return `${Math.round(n * 100)}%`;
}
