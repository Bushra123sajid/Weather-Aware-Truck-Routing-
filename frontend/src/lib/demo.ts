import type { IntervalMiles, Place, Scenario } from '../api/types';

export const DEMO_SCENARIO: Scenario = 'winter_storm';
export const DEMO_NOTE = 'Simulated winter storm. This is not real weather.';

export const DEMO_TRIP: {
  origin: Place;
  destination: Place;
  loadLb: number;
  intervalMiles: IntervalMiles;
} = {
  origin: { label: 'Denver, Colorado, United States', lat: 39.7392, lng: -104.9903 },
  destination: { label: 'Chicago, Illinois, United States', lat: 41.8781, lng: -87.6298 },
  loadLb: 45_000,
  intervalMiles: 25,
};

/** Next whole hour at least two hours from now. */
export function demoDeparture(now = new Date()): Date {
  const d = new Date(now.getTime() + 2 * 3600_000);
  if (d.getMinutes() || d.getSeconds() || d.getMilliseconds()) {
    d.setHours(d.getHours() + 1, 0, 0, 0);
  }
  return d;
}
