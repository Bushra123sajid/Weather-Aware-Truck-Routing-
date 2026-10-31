import { memo } from 'react';
import type { PlannedRoute } from '../api/types';
import { RISK_SCORES, UNKNOWN_META, riskMeta } from '../lib/risk';
import { routeStyle } from '../lib/routeStyle';
import { RiskDot } from './RiskIcon';

const LEVELS = [...RISK_SCORES.map((s) => riskMeta(s)), UNKNOWN_META];

/** Risk levels in the same icon/colour form as markers and chips. */
export function RiskScale() {
  return (
    <div className="risk-scale" aria-label="Risk levels">
      {LEVELS.map((m) => (
        <span key={m.label}>
          <RiskDot risk={m.score} size={14} />
          {m.label}
        </span>
      ))}
    </div>
  );
}

export const Legend = memo(function Legend({ routes }: { routes: PlannedRoute[] }) {
  return (
    <div className="legend" aria-label="Map legend">
      <div className="legend__group">
        <span className="legend__title">Risk</span>
        {LEVELS.map((m) => (
          <span key={m.label} className="legend__item">
            <RiskDot risk={m.score} />
            {m.label}
          </span>
        ))}
      </div>
      {routes.length > 0 && (
        <div className="legend__group">
          <span className="legend__title">Routes</span>
          {routes.map((r, i) => {
            const s = routeStyle(i);
            return (
              <span key={r.id} className="legend__item">
                <span
                  className={`route-swatch route-swatch--${s.pattern}`}
                  style={{ borderColor: s.color }}
                  aria-hidden="true"
                />
                {r.name}
                {r.recommended && <span className="badge">Recommended</span>}
              </span>
            );
          })}
        </div>
      )}
    </div>
  );
});
