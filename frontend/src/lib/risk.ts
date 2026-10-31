/**
 * Risk levels, colours and client-side classifiers.
 *
 * Thresholds mirror backend/apps/risk/rules.py; risk.test.ts uses the same boundary
 * table as the backend tests. The server stays authoritative for checkpoints and the
 * heatmap's overall layer. These functions drive the single-factor heatmap layers.
 */
import type { Driver, RiskScore } from '../api/types';

export interface RiskMeta {
  score: RiskScore | null;
  label: string;
  color: string;
  text: string;
}

// Each background meets WCAG AA contrast against its text colour. Every use also
// shows a label and a distinct icon, so colour is never the only cue.
export const RISK_META: Record<RiskScore, RiskMeta> = {
  1: { score: 1, label: 'Low', color: '#15803d', text: '#ffffff' },
  2: { score: 2, label: 'Moderate', color: '#facc15', text: '#1f2937' },
  3: { score: 3, label: 'High', color: '#f97316', text: '#1f2937' },
  4: { score: 4, label: 'Severe', color: '#b91c1c', text: '#ffffff' },
  5: { score: 5, label: 'No Travel', color: '#581c87', text: '#ffffff' },
};

export const UNKNOWN_META: RiskMeta = {
  score: null,
  label: 'Unknown',
  color: '#6b7280',
  text: '#ffffff',
};

export const RISK_SCORES: RiskScore[] = [1, 2, 3, 4, 5];

export function riskMeta(score: number | null | undefined): RiskMeta {
  return score && score >= 1 && score <= 5 ? RISK_META[score as RiskScore] : UNKNOWN_META;
}

export const DRIVER_LABEL: Record<Driver, string> = {
  wind: 'Wind',
  rain: 'Rain',
  snow: 'Snow',
  none: 'Clear',
  unknown: 'No data',
};

export function classifyWind(mph: number): RiskScore {
  if (mph >= 55) return 5;
  if (mph >= 45) return 4;
  if (mph >= 35) return 3;
  if (mph >= 25) return 2;
  return 1;
}

export function classifyRain(inHr: number): RiskScore {
  if (inHr > 1.0) return 5;
  if (inHr >= 0.5) return 4;
  if (inHr >= 0.25) return 3;
  if (inHr >= 0.1) return 2;
  return 1;
}

export function classifySnow(inHr: number): RiskScore {
  if (inHr > 3.0) return 5;
  if (inHr >= 2.0) return 4;
  if (inHr >= 1.0) return 3;
  if (inHr >= 0.5) return 2;
  return 1;
}

/** Wind level after the load rules; the worse of base and load-adjusted level. */
export function windLevel(mph: number, loadLb: number): RiskScore {
  const base = classifyWind(mph);
  let adjusted: RiskScore | null = null;
  if (mph >= 55) adjusted = 5;
  else if (mph >= 45 && loadLb > 30_000) adjusted = 5;
  else if (mph >= 35 && loadLb > 40_000) adjusted = 4;
  return adjusted !== null && adjusted > base ? adjusted : base;
}

export type HeatMetric = 'overall' | 'wind' | 'rain' | 'snow';

export function overallLevel(
  wind: number | null,
  rain: number | null,
  snow: number | null,
  loadLb: number,
): RiskScore | null {
  if (wind == null || rain == null || snow == null) return null;
  return Math.max(windLevel(wind, loadLb), classifyRain(rain), classifySnow(snow)) as RiskScore;
}
