import { useCallback, useEffect, useMemo, useState } from 'react';
import { LoaderCircle, Truck } from 'lucide-react';
import { ApiError } from './api/client';
import type { PlanRequest, Scenario } from './api/types';
import { AppHeader } from './components/AppHeader';
import { Banner, ResultsSkeleton } from './components/Banners';
import { DemoBanner } from './components/DemoBanner';
import { HeatmapControls } from './components/HeatmapControls';
import { Legend } from './components/Legend';
import { PlanForm } from './components/PlanForm';
import { ResultsPanel } from './components/ResultsPanel';
import { useHeatmap, usePlan } from './hooks/useApi';
import { useDebouncedValue } from './hooks/useDebouncedValue';
import { buildCells } from './lib/heat';
import type { HeatMetric } from './lib/risk';
import { MapView } from './map/MapView';

const SLIDER_DEBOUNCE_MS = 60;

export default function App() {
  const planMutation = usePlan();
  const plan = planMutation.data;
  const heatmap = useHeatmap(plan);

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showAllCheckpoints, setShowAllCheckpoints] = useState(false);
  const [heatVisible, setHeatVisible] = useState(true);
  const [metric, setMetric] = useState<HeatMetric>('overall');
  const [hourInput, setHourInput] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [errorDismissed, setErrorDismissed] = useState(false);
  const [scenario, setScenario] = useState<Scenario | null>(null);

  // The slider label updates immediately; the canvas follows a debounced value.
  const hour = useDebouncedValue(hourInput, SLIDER_DEBOUNCE_MS);

  useEffect(() => {
    if (plan) setSelectedId(plan.recommended_route_id);
  }, [plan]);

  // Jump the slider to the departure hour when a new heatmap arrives.
  useEffect(() => {
    if (heatmap.data) {
      setHourInput(heatmap.data.departure_index ?? 0);
      setPlaying(false);
    }
  }, [heatmap.data]);

  const { mutate, reset } = planMutation;
  const exitDemo = useCallback(() => {
    setScenario(null);
    reset();
  }, [reset]);
  const onSubmit = useCallback(
    (req: PlanRequest) => {
      setErrorDismissed(false);
      mutate(req);
    },
    [mutate],
  );

  const cells = useMemo(
    () =>
      heatmap.data && plan
        ? buildCells(heatmap.data.points, hour, metric, plan.load_weight_lb)
        : [],
    [heatmap.data, hour, metric, plan],
  );
  const heat = useMemo(
    () => ({ cells, spacingMi: heatmap.data?.spacing_mi ?? 10, visible: heatVisible }),
    [cells, heatmap.data?.spacing_mi, heatVisible],
  );

  const planError =
    planMutation.error instanceof ApiError
      ? planMutation.error.message
      : planMutation.error
        ? 'Planning failed. Check the inputs and try again.'
        : null;

  return (
    <div className="app">
      <AppHeader />
      <aside className="sidebar">
        <h1 className="sr-only">RouteWise trip planner</h1>
        <PlanForm
          onSubmit={onSubmit}
          loading={planMutation.isPending}
          scenario={scenario}
          onScenarioChange={setScenario}
        />
        {scenario && <DemoBanner onExit={exitDemo} />}
        {planError && !errorDismissed && (
          <Banner kind="error" onDismiss={() => setErrorDismissed(true)}>
            {planError}
          </Banner>
        )}
        {planMutation.isPending && <ResultsSkeleton />}
        {plan && !planMutation.isPending && (
          <ResultsPanel plan={plan} selectedId={selectedId} onSelect={setSelectedId} />
        )}
        {!plan && !planMutation.isPending && (
          <p className="empty-hint">
            <Truck size={16} aria-hidden="true" />
            Enter a trip to compare three routes by weather risk, load and travel time.
          </p>
        )}
      </aside>

      <main className="map-wrap" aria-label="Map">
        <MapView
          plan={plan}
          selectedId={selectedId}
          onSelect={setSelectedId}
          showAllCheckpoints={showAllCheckpoints}
          heat={heat}
        />
        {planMutation.isPending && (
          <div className="map-overlay" role="status">
            <LoaderCircle className="spin" size={16} aria-hidden="true" />
            Fetching routes and forecasts
          </div>
        )}
        {scenario && <DemoBanner onExit={exitDemo} variant="map" />}
        <Legend routes={plan?.routes ?? []} />
        {plan && (
          <HeatmapControls
            hours={heatmap.data?.hours ?? []}
            hour={hourInput}
            onHour={setHourInput}
            departureIndex={heatmap.data?.departure_index ?? null}
            metric={metric}
            onMetric={setMetric}
            visible={heatVisible}
            onVisible={setHeatVisible}
            playing={playing}
            onPlaying={setPlaying}
            loading={heatmap.isLoading}
            error={
              heatmap.error
                ? `Heatmap is unavailable: ${(heatmap.error as Error).message}`
                : (heatmap.data?.warnings[0] ?? null)
            }
            showAllCheckpoints={showAllCheckpoints}
            onShowAllCheckpoints={setShowAllCheckpoints}
            simulated={Boolean(heatmap.data?.demo)}
          />
        )}
      </main>
    </div>
  );
}
