import { describe, expect, it } from 'vitest';
import { departureError, formatDuration } from './format';

describe('format helpers', () => {
  it('formats durations', () => {
    expect(formatDuration(45)).toBe('45 min');
    expect(formatDuration(125)).toBe('2 h 05 min');
  });

  it('validates the departure window', () => {
    const now = Date.parse('2026-11-01T12:00:00Z');
    expect(departureError('2026-11-01T13:00:00Z', now)).toBeNull();
    expect(departureError('2026-11-01T10:00:00Z', now)).toMatch(/past/);
    expect(departureError('2026-11-03T13:00:00Z', now)).toMatch(/48 hours/);
    expect(departureError('', now)).toMatch(/Choose/);
  });
});
