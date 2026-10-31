import { memo, useEffect } from 'react';
import { ChevronDown, CloudRain, Gauge, Pause, Play, Snowflake, Wind } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { formatHourLabel } from '../lib/format';
import type { HeatMetric } from '../lib/risk';
import { RiskScale } from './Legend';

interface Props {
  hours: string[];
  hour: number;
  onHour: (h: number) => void;
  departureIndex: number | null;
  metric: HeatMetric;
  onMetric: (m: HeatMetric) => void;
  visible: boolean;
  onVisible: (v: boolean) => void;
  playing: boolean;
  onPlaying: (p: boolean) => void;
  loading: boolean;
  error: string | null;
  showAllCheckpoints: boolean;
  onShowAllCheckpoints: (v: boolean) => void;
  simulated?: boolean;
}

const METRICS: { id: HeatMetric; label: string; icon: LucideIcon }[] = [
  { id: 'overall', label: 'Overall risk', icon: Gauge },
  { id: 'wind', label: 'Wind', icon: Wind },
  { id: 'rain', label: 'Rain', icon: CloudRain },
  { id: 'snow', label: 'Snow', icon: Snowflake },
];

const PLAY_STEP_MS = 650;

export const HeatmapControls = memo(function HeatmapControls(p: Props) {
  const max = Math.max(0, p.hours.length - 1);
  const { playing, onHour, onPlaying, hour } = p;

  useEffect(() => {
    if (!playing || max === 0) return;
    const id = window.setInterval(() => onHour(hour >= max ? 0 : hour + 1), PLAY_STEP_MS);
    return () => window.clearInterval(id);
  }, [playing, hour, max, onHour]);

  const ready = p.hours.length > 0;
  const label = ready ? formatHourLabel(p.hours[p.hour]) : '';

  return (
    <div className="heat-controls" role="group" aria-label="Weather heatmap controls">
      <div className="heat-controls__top">
        <label className="toggle">
          <input
            type="checkbox"
            checked={p.visible}
            onChange={(e) => p.onVisible(e.target.checked)}
          />
          Heatmap
        </label>
        <div className="segmented segmented--small" role="radiogroup" aria-label="Heatmap metric">
          {METRICS.map(({ id, label: text, icon: Icon }) => (
            <label key={id} className={p.metric === id ? 'checked' : undefined}>
              <input
                type="radio"
                name="heat-metric"
                checked={p.metric === id}
                onChange={() => p.onMetric(id)}
                disabled={!p.visible}
              />
              <Icon size={13} aria-hidden="true" />
              {text}
            </label>
          ))}
        </div>
        {p.simulated && <span className="sim-label">Simulated</span>}
        <label className="toggle">
          <input
            type="checkbox"
            checked={p.showAllCheckpoints}
            onChange={(e) => p.onShowAllCheckpoints(e.target.checked)}
          />
          All checkpoints
        </label>
      </div>

      {p.loading && <div className="heat-controls__status">Loading 48-hour forecast</div>}
      {p.error && (
        <div className="heat-controls__status heat-controls__status--error">{p.error}</div>
      )}

      {ready && (
        <div className="heat-controls__slider">
          <button
            type="button"
            className="btn-icon"
            onClick={() => onPlaying(!playing)}
            aria-label={playing ? 'Pause' : 'Play'}
            disabled={!p.visible}
          >
            {playing ? (
              <Pause size={16} aria-hidden="true" />
            ) : (
              <Play size={16} aria-hidden="true" />
            )}
          </button>
          <div className="slider-wrap">
            <input
              type="range"
              min={0}
              max={max}
              step={1}
              value={p.hour}
              onChange={(e) => {
                onPlaying(false);
                onHour(Number(e.target.value));
              }}
              aria-label="Forecast hour"
              aria-valuetext={`${label}, plus ${p.hour} hours`}
              disabled={!p.visible}
            />
            {p.departureIndex != null && (
              <button
                type="button"
                className="departure-tick"
                style={{ left: `${(p.departureIndex / max) * 100}%` }}
                onClick={() => onHour(p.departureIndex!)}
                title="Go to departure hour"
                aria-label="Go to departure hour"
              >
                <ChevronDown size={16} strokeWidth={3} aria-hidden="true" />
              </button>
            )}
          </div>
          <output className="heat-controls__time" aria-live="polite">
            <strong>{label}</strong>
            <span className="muted">
              {' '}
              +{p.hour} h{p.departureIndex === p.hour ? ', departure' : ''}
            </span>
          </output>
        </div>
      )}
      {ready && p.visible && <RiskScale />}
    </div>
  );
});
