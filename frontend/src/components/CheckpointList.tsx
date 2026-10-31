import { memo } from 'react';
import { ChevronDown } from 'lucide-react';
import type { PlannedRoute } from '../api/types';
import { formatDateTime, formatNumber } from '../lib/format';
import { RiskChip } from './RiskChip';

interface Props {
  route: PlannedRoute;
  open: boolean;
  onToggle: (open: boolean) => void;
}

export const CheckpointList = memo(function CheckpointList({ route, open, onToggle }: Props) {
  return (
    <details
      className="checkpoints"
      open={open}
      onToggle={(e) => onToggle((e.currentTarget as HTMLDetailsElement).open)}
    >
      <summary>
        <ChevronDown size={16} aria-hidden="true" />
        {route.name} checkpoints ({route.checkpoints.length})
      </summary>
      {open && (
        <div className="table-scroll">
          <table className="cp-table">
            <thead>
              <tr>
                <th scope="col">Mile</th>
                <th scope="col">ETA (local)</th>
                <th scope="col">Wind mph</th>
                <th scope="col">Rain in/h</th>
                <th scope="col">Snow in/h</th>
                <th scope="col">Risk</th>
              </tr>
            </thead>
            <tbody>
              {route.checkpoints.map((c) => (
                <tr key={c.index}>
                  <td>{c.mile.toFixed(0)}</td>
                  <td>{formatDateTime(c.eta, c.timezone)}</td>
                  <td>
                    {formatNumber(c.wind_mph, 0)}
                    {c.gust_mph != null && (
                      <span className="muted"> (gust {c.gust_mph.toFixed(0)})</span>
                    )}
                  </td>
                  <td>{formatNumber(c.rain_in_hr, 2)}</td>
                  <td>{formatNumber(c.snow_in_hr, 2)}</td>
                  <td>
                    <RiskChip risk={c.risk} driver={c.driver} loadAdjusted={c.load_adjusted} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </details>
  );
});
