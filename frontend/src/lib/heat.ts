import type { HeatmapPoint } from '../api/types';
import type { HeatCell } from '../map/RiskHeatLayer';
import { classifyRain, classifySnow, windLevel, type HeatMetric } from './risk';

/** Level for one grid point at one hour for the chosen metric (load applied to wind). */
export function cellLevel(
  p: HeatmapPoint,
  hour: number,
  metric: HeatMetric,
  loadLb: number,
): number | null {
  switch (metric) {
    case 'overall':
      return p.risk[hour] ?? null;
    case 'wind': {
      const v = p.wind[hour];
      return v == null ? null : windLevel(v, loadLb);
    }
    case 'rain': {
      const v = p.rain[hour];
      return v == null ? null : classifyRain(v);
    }
    case 'snow': {
      const v = p.snow[hour];
      return v == null ? null : classifySnow(v);
    }
  }
}

export function buildCells(
  points: HeatmapPoint[],
  hour: number,
  metric: HeatMetric,
  loadLb: number,
): HeatCell[] {
  return points.map((p) => ({ lat: p.lat, lng: p.lng, level: cellLevel(p, hour, metric, loadLb) }));
}
