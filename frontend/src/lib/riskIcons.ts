import {
  Ban,
  CircleAlert,
  CircleCheck,
  CircleHelp,
  OctagonAlert,
  TriangleAlert,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

// One icon per level, shared by chips, legends and map markers.
const RISK_ICONS: Record<number, LucideIcon> = {
  1: CircleCheck,
  2: CircleAlert,
  3: TriangleAlert,
  4: OctagonAlert,
  5: Ban,
};

export function riskIcon(score: number | null | undefined): LucideIcon {
  return (score && RISK_ICONS[score]) || CircleHelp;
}
