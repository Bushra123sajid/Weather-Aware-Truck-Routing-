import { memo } from 'react';
import { Clock, CloudRain, Snowflake, Wind } from 'lucide-react';
import type { Checkpoint, PlannedRoute } from '../api/types';
import { RiskChip } from '../components/RiskChip';
import { formatDateTime, formatDuration, formatMiles, formatNumber } from '../lib/format';

export const CheckpointPopup = memo(function CheckpointPopup({
  cp,
  routeName,
}: {
  cp: Checkpoint;
  routeName: string;
}) {
  return (
    <div className="cp-popup">
      <strong>
        {routeName}, mile {cp.mile.toFixed(0)}
      </strong>
      <span className="cp-popup__row">
        <Clock size={14} aria-hidden="true" />
        ETA {formatDateTime(cp.eta, cp.timezone)}
      </span>
      <span className="cp-popup__row">
        <Wind size={14} aria-hidden="true" />
        Wind {formatNumber(cp.wind_mph, 0, ' mph')}
        {cp.gust_mph != null && `, gusts ${cp.gust_mph.toFixed(0)}`}
      </span>
      <span className="cp-popup__row">
        <CloudRain size={14} aria-hidden="true" />
        Rain {formatNumber(cp.rain_in_hr, 2, ' in/h')}
      </span>
      <span className="cp-popup__row">
        <Snowflake size={14} aria-hidden="true" />
        Snow {formatNumber(cp.snow_in_hr, 2, ' in/h')}
      </span>
      <span className="cp-popup__risk">
        <RiskChip risk={cp.risk} driver={cp.driver} loadAdjusted={cp.load_adjusted} />
      </span>
    </div>
  );
});

export function RoutePopup({ route }: { route: PlannedRoute }) {
  return (
    <div className="cp-popup">
      <strong>
        {route.name}
        {route.recommended && <span className="badge">Recommended</span>}
      </strong>
      <span>
        {formatMiles(route.distance_mi)}, {formatDuration(route.duration_min)}, rank {route.rank}
      </span>
      <span>
        Severe {route.metrics.severe_miles.toFixed(1)} mi, High{' '}
        {route.metrics.high_miles.toFixed(1)} mi
      </span>
    </div>
  );
}
