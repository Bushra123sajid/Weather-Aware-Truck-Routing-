import { memo } from 'react';
import type { PlannedRoute } from '../api/types';
import { formatDuration, formatMiles } from '../lib/format';
import { routeStyle } from '../lib/routeStyle';
import { RiskChip } from './RiskChip';

interface Props {
  routes: PlannedRoute[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export const RouteComparison = memo(function RouteComparison({
  routes,
  selectedId,
  onSelect,
}: Props) {
  const anyNoTravel = routes.some((r) => r.metrics.no_travel_miles > 0);
  const sorted = [...routes].sort((a, b) => a.rank - b.rank);
  return (
    <div className="table-scroll">
      <table className="compare-table">
        <caption className="sr-only">Routes ranked best first</caption>
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Route</th>
            <th scope="col">Distance</th>
            <th scope="col">Duration</th>
            {anyNoTravel && <th scope="col">No Travel</th>}
            <th scope="col">Severe</th>
            <th scope="col">High</th>
            <th scope="col">Avg risk</th>
            <th scope="col">Worst</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const idx = routes.findIndex((x) => x.id === r.id);
            const style = routeStyle(idx);
            const m = r.metrics;
            const selected = r.id === selectedId;
            return (
              <tr
                key={r.id}
                className={`${selected ? 'selected' : ''} ${r.recommended ? 'recommended' : ''}`}
                aria-selected={selected}
                tabIndex={0}
                onClick={() => onSelect(r.id)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    onSelect(r.id);
                  }
                }}
              >
                <td>#{r.rank}</td>
                <th scope="row">
                  <span
                    className={`route-swatch route-swatch--${style.pattern}`}
                    style={{ borderColor: style.color }}
                    aria-hidden="true"
                  />
                  {r.name}
                  {r.recommended && <span className="badge">Recommended</span>}
                </th>
                <td>{formatMiles(r.distance_mi)}</td>
                <td>{formatDuration(r.duration_min)}</td>
                {anyNoTravel && <td>{formatMiles(m.no_travel_miles, 1)}</td>}
                <td>{formatMiles(m.severe_miles, 1)}</td>
                <td>{formatMiles(m.high_miles, 1)}</td>
                <td>{m.avg_risk == null ? '-' : m.avg_risk.toFixed(2)}</td>
                <td>
                  <RiskChip risk={m.max_risk} compact />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
});
