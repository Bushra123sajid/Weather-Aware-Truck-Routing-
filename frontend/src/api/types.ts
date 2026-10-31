/** Wire types for the Django API. Keep in sync with backend serializers/services. */

export type RiskScore = 1 | 2 | 3 | 4 | 5;
export type Driver = 'wind' | 'rain' | 'snow' | 'none' | 'unknown';
export type IntervalMiles = 10 | 25 | 50;
export type Scenario = 'winter_storm';

export interface Place {
  label: string;
  lat: number;
  lng: number;
}

export interface Checkpoint {
  index: number;
  lat: number;
  lng: number;
  mile: number;
  segment_miles: number;
  eta: string;
  timezone: string | null;
  forecast_hour: string | null;
  wind_mph: number | null;
  gust_mph: number | null;
  rain_in_hr: number | null;
  snow_in_hr: number | null;
  risk: RiskScore | null;
  risk_label: string;
  driver: Driver;
  load_adjusted: boolean;
  factor_levels: { wind: RiskScore; rain: RiskScore; snow: RiskScore } | null;
}

export interface RouteMetrics {
  route_id: string;
  name: string;
  distance_mi: number;
  duration_min: number;
  low_miles: number;
  moderate_miles: number;
  high_miles: number;
  severe_miles: number;
  no_travel_miles: number;
  unknown_miles: number;
  avg_risk: number | null;
  max_risk: RiskScore | null;
  worst_index: number | null;
  worst_checkpoint: Pick<
    Checkpoint,
    'index' | 'mile' | 'eta' | 'risk' | 'risk_label' | 'driver'
  > | null;
}

export interface PlannedRoute {
  id: string;
  name: string;
  provider: string;
  profile: string;
  /** Google encoded polyline, precision 5. */
  geometry: string;
  distance_mi: number;
  duration_min: number;
  arrival_time: string;
  checkpoints: Checkpoint[];
  metrics: RouteMetrics;
  rank: number;
  recommended: boolean;
}

export interface PlanRequest {
  origin: Place | string;
  destination: Place | string;
  departure_time: string;
  load_weight_lb: number;
  interval_miles: IntervalMiles;
  scenario?: Scenario | null;
}

export interface DemoFields {
  demo?: boolean;
  scenario?: Scenario;
  scenario_note?: string;
}

export interface PlanResponse extends DemoFields {
  plan_id: string;
  origin: Place;
  destination: Place;
  departure_time: string;
  load_weight_lb: number;
  interval_miles: IntervalMiles;
  routes: PlannedRoute[];
  recommended_route_id: string;
  ranking: string[];
  explanation: string;
  all_routes_no_travel: boolean;
  notices: string[];
  warnings: string[];
}

export interface HeatmapRequest {
  polylines: string[];
  load_weight_lb: number;
  start_time?: string;
  scenario?: Scenario | null;
}

export interface HeatmapPoint {
  lat: number;
  lng: number;
  wind: (number | null)[];
  rain: (number | null)[];
  snow: (number | null)[];
  risk: (RiskScore | null)[];
}

export interface HeatmapResponse extends DemoFields {
  hours: string[];
  points: HeatmapPoint[];
  warnings: string[];
  spacing_mi: number;
  buffer_mi: number;
  departure_index: number | null;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}
