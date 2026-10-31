import { describe, expect, it } from 'vitest';
import type { HeatmapPoint } from '../api/types';
import { buildCells, cellLevel } from './heat';

const point: HeatmapPoint = {
  lat: 35,
  lng: -100,
  wind: [40, 10],
  rain: [0, 0.3],
  snow: [0, null],
  risk: [4, null],
};

describe('heat cell levels', () => {
  it('uses server risk for overall and client thresholds per metric', () => {
    expect(cellLevel(point, 0, 'overall', 45_000)).toBe(4);
    expect(cellLevel(point, 0, 'wind', 45_000)).toBe(4); // load rule
    expect(cellLevel(point, 0, 'wind', 10_000)).toBe(3);
    expect(cellLevel(point, 1, 'rain', 0)).toBe(3);
    expect(cellLevel(point, 1, 'snow', 0)).toBeNull();
  });

  it('builds one cell per point', () => {
    expect(buildCells([point, point], 1, 'overall', 0)).toHaveLength(2);
  });
});
