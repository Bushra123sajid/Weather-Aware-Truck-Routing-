import { memo } from 'react';
import type { Driver } from '../api/types';
import { DRIVER_LABEL, riskMeta } from '../lib/risk';
import { riskIcon } from '../lib/riskIcons';

interface Props {
  risk: number | null;
  driver?: Driver;
  loadAdjusted?: boolean;
  compact?: boolean;
}

export const RiskChip = memo(function RiskChip({ risk, driver, loadAdjusted, compact }: Props) {
  const meta = riskMeta(risk);
  const Icon = riskIcon(risk);
  const showDriver = driver && driver !== 'none' && driver !== 'unknown';
  const driverText = showDriver
    ? `${DRIVER_LABEL[driver]}${loadAdjusted ? ' + load' : ''}`
    : undefined;
  const title = `Risk: ${meta.label}${driverText ? ` (driven by ${driverText.toLowerCase()})` : ''}`;
  return (
    <span
      className={`risk-chip${compact ? ' risk-chip--compact' : ''}`}
      style={{ background: meta.color, color: meta.text }}
      title={title}
      aria-label={title}
    >
      <Icon size={12} strokeWidth={2.5} aria-hidden="true" />
      <span>
        {meta.label}
        {driverText && !compact && <span className="risk-chip__driver">{`, ${driverText}`}</span>}
      </span>
    </span>
  );
});
