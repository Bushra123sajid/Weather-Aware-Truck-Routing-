import { CloudSnow } from 'lucide-react';
import { DEMO_NOTE } from '../lib/demo';

interface Props {
  onExit: () => void;
  variant?: 'panel' | 'map';
}

export function DemoBanner({ onExit, variant = 'panel' }: Props) {
  return (
    <div className={`demo-banner demo-banner--${variant}`} role="status">
      <CloudSnow size={16} aria-hidden="true" />
      <span className="demo-banner__text">{DEMO_NOTE}</span>
      <button type="button" className="demo-banner__exit" onClick={onExit}>
        Use live data
      </button>
    </div>
  );
}
