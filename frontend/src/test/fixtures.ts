import type { Checkpoint, PlannedRoute, RouteMetrics } from '../api/types';

export function metrics(overrides: Partial<RouteMetrics> = {}): RouteMetrics {
  return {
    route_id: 'r1',
    name: 'Route 1',
    distance_mi: 200,
    duration_min: 210,
    low_miles: 200,
    moderate_miles: 0,
    high_miles: 0,
    severe_miles: 0,
    no_travel_miles: 0,
    unknown_miles: 0,
    avg_risk: 1,
    max_risk: 1,
    worst_index: 0,
    worst_checkpoint: null,
    ...overrides,
  };
}

export function checkpoint(overrides: Partial<Checkpoint> = {}): Checkpoint {
  return {
    index: 0,
    lat: 35,
    lng: -100,
    mile: 0,
    segment_miles: 12.5,
    eta: '2026-11-01T15:00:00Z',
    timezone: 'America/Chicago',
    forecast_hour: '2026-11-01T15:00:00Z',
    wind_mph: 12,
    gust_mph: 18,
    rain_in_hr: 0,
    snow_in_hr: 0,
    risk: 1,
    risk_label: 'Low',
    driver: 'none',
    load_adjusted: false,
    factor_levels: { wind: 1, rain: 1, snow: 1 },
    ...overrides,
  };
}

export function route(id: string, rank: number, m: Partial<RouteMetrics> = {}): PlannedRoute {
  const n = id.slice(1);
  return {
    id,
    name: `Route ${n}`,
    provider: 'osrm',
    profile: 'driving',
    geometry: '_p~iF~ps|U_ulLnnqC',
    distance_mi: 200,
    duration_min: 210,
    arrival_time: '2026-11-01T18:30:00Z',
    checkpoints: [checkpoint()],
    metrics: metrics({ route_id: id, name: `Route ${n}`, ...m }),
    rank,
    recommended: rank === 1,
  };
}
