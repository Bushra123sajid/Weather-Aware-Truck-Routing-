import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RiskChip } from './RiskChip';

describe('RiskChip', () => {
  it('shows label, icon and driving factor (not colour alone)', () => {
    render(<RiskChip risk={4} driver="wind" loadAdjusted />);
    const chip = screen.getByLabelText(/Risk: Severe/);
    expect(chip).toHaveTextContent('Severe');
    expect(chip.querySelector('svg')).not.toBeNull();
    expect(chip).toHaveTextContent('Wind + load');
  });

  it('hides the driver when conditions are clear', () => {
    render(<RiskChip risk={1} driver="none" />);
    expect(screen.getByLabelText('Risk: Low')).not.toHaveTextContent('Clear');
  });

  it('renders unknown risk', () => {
    render(<RiskChip risk={null} driver="unknown" />);
    expect(screen.getByLabelText('Risk: Unknown')).toHaveTextContent('Unknown');
  });
});
