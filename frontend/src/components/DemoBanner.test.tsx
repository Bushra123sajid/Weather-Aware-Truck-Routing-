import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { DemoBanner } from './DemoBanner';

describe('DemoBanner', () => {
  it('labels the data as simulated and offers a way back to live data', async () => {
    const onExit = vi.fn();
    render(<DemoBanner onExit={onExit} />);
    expect(screen.getByRole('status')).toHaveTextContent(
      'Simulated winter storm. This is not real weather.',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Use live data' }));
    expect(onExit).toHaveBeenCalledOnce();
  });
});
