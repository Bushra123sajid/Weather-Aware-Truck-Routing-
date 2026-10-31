import { useState } from 'react';
import { CloudSnow, LoaderCircle } from 'lucide-react';
import type { IntervalMiles, PlanRequest, Scenario } from '../api/types';
import { DEMO_SCENARIO, DEMO_TRIP, demoDeparture } from '../lib/demo';
import { defaultDeparture, departureError, toLocalInputValue } from '../lib/format';
import { LocationInput, type LocationValue } from './LocationInput';

interface Props {
  onSubmit: (req: PlanRequest) => void;
  loading: boolean;
  scenario: Scenario | null;
  onScenarioChange: (scenario: Scenario | null) => void;
}

const INTERVALS: IntervalMiles[] = [10, 25, 50];
const MAX_LOAD = 200_000;
const EMPTY: LocationValue = { text: '', place: null };

export function PlanForm({ onSubmit, loading, scenario, onScenarioChange }: Props) {
  const [origin, setOrigin] = useState<LocationValue>(EMPTY);
  const [destination, setDestination] = useState<LocationValue>(EMPTY);
  const [departure, setDeparture] = useState(() => toLocalInputValue(defaultDeparture()));
  const [load, setLoad] = useState('40000');
  const [interval, setIntervalMiles] = useState<IntervalMiles>(25);
  const [touched, setTouched] = useState(false);
  const demo = scenario !== null;

  const loadNum = Number(load);
  const errors = {
    origin: origin.text.trim().length < 2 ? 'Enter an origin.' : null,
    destination:
      destination.text.trim().length < 2
        ? 'Enter a destination.'
        : destination.text.trim().toLowerCase() === origin.text.trim().toLowerCase()
          ? 'Destination must differ from origin.'
          : null,
    departure: departureError(departure),
    load:
      load === '' || Number.isNaN(loadNum) || loadNum < 0 || loadNum > MAX_LOAD
        ? `Enter a load between 0 and ${MAX_LOAD.toLocaleString()} lb.`
        : null,
  };
  const valid = Object.values(errors).every((e) => e === null);
  const show = (e: string | null) => (touched ? e : null);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    setTouched(true);
    if (!valid || loading) return;
    onSubmit({
      origin: origin.place ?? origin.text.trim(),
      destination: destination.place ?? destination.text.trim(),
      departure_time: new Date(departure).toISOString(),
      load_weight_lb: loadNum,
      interval_miles: interval,
      scenario,
    });
  };

  const loadDemo = () => {
    const dep = demoDeparture();
    setOrigin({ text: DEMO_TRIP.origin.label, place: DEMO_TRIP.origin });
    setDestination({ text: DEMO_TRIP.destination.label, place: DEMO_TRIP.destination });
    setDeparture(toLocalInputValue(dep));
    setLoad(String(DEMO_TRIP.loadLb));
    setIntervalMiles(DEMO_TRIP.intervalMiles);
    setTouched(false);
    onScenarioChange(DEMO_SCENARIO);
    onSubmit({
      origin: DEMO_TRIP.origin,
      destination: DEMO_TRIP.destination,
      departure_time: dep.toISOString(),
      load_weight_lb: DEMO_TRIP.loadLb,
      interval_miles: DEMO_TRIP.intervalMiles,
      scenario: DEMO_SCENARIO,
    });
  };

  return (
    <form className="plan-form" onSubmit={submit} noValidate aria-label="Trip details">
      <LocationInput
        label="Origin"
        placeholder="City or address"
        value={origin}
        onChange={setOrigin}
        error={show(errors.origin)}
        disabled={demo}
      />
      <LocationInput
        label="Destination"
        placeholder="City or address"
        value={destination}
        onChange={setDestination}
        error={show(errors.destination)}
        disabled={demo}
      />
      <div className="field-row">
        <div className="field">
          <label htmlFor="departure">Departure time</label>
          <input
            id="departure"
            type="datetime-local"
            value={departure}
            onChange={(e) => setDeparture(e.target.value)}
            aria-invalid={Boolean(show(errors.departure))}
          />
        </div>
        <div className="field">
          <label htmlFor="load">Load weight (lb)</label>
          <input
            id="load"
            type="number"
            inputMode="numeric"
            min={0}
            max={MAX_LOAD}
            step={500}
            value={load}
            onChange={(e) => setLoad(e.target.value)}
            aria-invalid={Boolean(show(errors.load))}
          />
        </div>
      </div>
      {show(errors.departure) && (
        <p className="field__error" role="alert">
          {errors.departure}
        </p>
      )}
      {show(errors.load) && (
        <p className="field__error" role="alert">
          {errors.load}
        </p>
      )}
      <fieldset className="field segmented">
        <legend>Checkpoint interval</legend>
        {INTERVALS.map((n) => (
          <label key={n} className={interval === n ? 'checked' : undefined}>
            <input
              type="radio"
              name="interval"
              value={n}
              checked={interval === n}
              onChange={() => setIntervalMiles(n)}
            />
            {n} mi
          </label>
        ))}
      </fieldset>
      <div className="form-actions">
        <button type="submit" className="btn btn-primary" disabled={loading} aria-busy={loading}>
          {loading && <LoaderCircle className="spin" size={16} aria-hidden="true" />}
          {loading ? 'Planning' : 'Plan route'}
        </button>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={loadDemo}
          disabled={loading}
          aria-pressed={demo}
        >
          <CloudSnow size={16} aria-hidden="true" />
          {demo ? 'Reload demo' : 'Load demo scenario'}
        </button>
      </div>
    </form>
  );
}
