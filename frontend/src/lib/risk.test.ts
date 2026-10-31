import { describe, expect, it } from 'vitest';
import { classifyRain, classifySnow, classifyWind, overallLevel, windLevel } from './risk';

// Same boundary table as backend/tests/test_risk_rules.py.
describe('risk thresholds (mirror of backend rules)', () => {
  it.each([
    [24.99, 1],
    [25, 2],
    [34.99, 2],
    [35, 3],
    [44.99, 3],
    [45, 4],
    [54.99, 4],
    [55, 5],
  ])('wind %s mph -> %s', (v, lvl) => expect(classifyWind(v)).toBe(lvl));

  it.each([
    [0.099, 1],
    [0.1, 2],
    [0.249, 2],
    [0.25, 3],
    [0.499, 3],
    [0.5, 4],
    [1.0, 4],
    [1.0001, 5],
  ])('rain %s in/h -> %s', (v, lvl) => expect(classifyRain(v)).toBe(lvl));

  it.each([
    [0.49, 1],
    [0.5, 2],
    [0.99, 2],
    [1.0, 3],
    [1.99, 3],
    [2.0, 4],
    [3.0, 4],
    [3.01, 5],
  ])('snow %s in/h -> %s', (v, lvl) => expect(classifySnow(v)).toBe(lvl));

  it.each([
    [55, 0, 5],
    [45, 30_001, 5],
    [45, 30_000, 4],
    [35, 40_001, 4],
    [35, 40_000, 3],
    [34.9, 80_000, 2],
  ])('load rules: wind %s mph, %s lb -> %s', (mph, load, lvl) =>
    expect(windLevel(mph, load)).toBe(lvl),
  );

  it('overall is the max of factors and null when data is missing', () => {
    expect(overallLevel(10, 0.3, 0.6, 0)).toBe(3);
    expect(overallLevel(40, 0, 0, 45_000)).toBe(4);
    expect(overallLevel(null, 0, 0, 0)).toBeNull();
  });
});
