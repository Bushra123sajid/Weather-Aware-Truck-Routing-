import { useState } from 'react';
import { Clock, MapPin, Route as RouteIcon, Weight } from 'lucide-react';
import type { PlanResponse } from '../api/types';
import { formatDateTime, formatDuration, formatMiles } from '../lib/format';
import { Banner } from './Banners';
import { CheckpointList } from './CheckpointList';
import { RiskChip } from './RiskChip';
import { RouteComparison } from './RouteComparison';

interface Props {
  plan: PlanResponse;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

export function ResultsPanel({ plan, selectedId, onSelect }: Props) {
  const recommended = plan.routes.find((r) => r.id === plan.recommended_route_id)!;
  const [openLists, setOpenLists] = useState<Record<string, boolean>>({});
  const m = recommended.metrics;

  return (
    <section className="results" aria-labelledby="results-heading">
      <h2 id="results-heading" className="sr-only">
        Results
      </h2>
      {plan.all_routes_no_travel && (
        <Banner kind="error">
          Every route crosses No Travel conditions. Consider a later departure.
        </Banner>
      )}
      {plan.notices.map((n) => (
        <Banner key={n} kind="info">
          {n}
        </Banner>
      ))}
      {plan.warnings.map((w) => (
        <Banner key={w} kind="warning">
          {w}
        </Banner>
      ))}

      <article className="rec-card" aria-label="Recommended route">
        <header>
          <span className="badge badge--lg">Recommended</span>
          <h3>{recommended.name}</h3>
          <RiskChip risk={m.max_risk} driver={m.worst_checkpoint?.driver} />
          {plan.demo && <span className="sim-label">Simulated</span>}
        </header>
        <div className="rec-card__stats">
          <span>
            <RouteIcon size={14} aria-hidden="true" />
            {formatMiles(recommended.distance_mi)}
          </span>
          <span>
            <Clock size={14} aria-hidden="true" />
            {formatDuration(recommended.duration_min)}
          </span>
          <span>
            <MapPin size={14} aria-hidden="true" />
            Arrives{' '}
            {formatDateTime(recommended.arrival_time, recommended.checkpoints.at(-1)?.timezone)}
          </span>
          <span>
            <Weight size={14} aria-hidden="true" />
            {plan.load_weight_lb.toLocaleString()} lb
          </span>
        </div>
        <p className="rec-card__why">{plan.explanation}</p>
      </article>

      <h3 className="section-title">Route comparison</h3>
      <RouteComparison routes={plan.routes} selectedId={selectedId} onSelect={onSelect} />

      <h3 className="section-title">Checkpoints</h3>
      {plan.routes.map((r) => (
        <CheckpointList
          key={r.id}
          route={r}
          open={Boolean(openLists[r.id])}
          onToggle={(open) => {
            setOpenLists((s) => ({ ...s, [r.id]: open }));
            if (open) onSelect(r.id);
          }}
        />
      ))}
    </section>
  );
}
