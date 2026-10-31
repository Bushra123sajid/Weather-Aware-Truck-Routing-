import { riskMeta } from '../lib/risk';
import { riskIcon } from '../lib/riskIcons';

interface Props {
  risk: number | null | undefined;
  size?: number;
}

/** Level icon on a disc in the level's colour. */
export function RiskDot({ risk, size = 16 }: Props) {
  const meta = riskMeta(risk);
  const Icon = riskIcon(risk);
  return (
    <span
      className="risk-dot"
      style={{ background: meta.color, color: meta.text, width: size, height: size }}
      aria-hidden="true"
    >
      <Icon size={Math.round(size * 0.7)} strokeWidth={2.5} />
    </span>
  );
}
