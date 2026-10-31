import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi } from 'vitest';
import type { Scenario } from '../api/types';
import { PlanForm } from './PlanForm';

function renderForm(scenario: Scenario | null = null) {
  const onSubmit = vi.fn();
  const onScenarioChange = vi.fn();
  render(
    <QueryClientProvider client={new QueryClient()}>
      <PlanForm
        onSubmit={onSubmit}
        loading={false}
        scenario={scenario}
        onScenarioChange={onScenarioChange}
      />
    </QueryClientProvider>,
  );
  return { onSubmit, onScenarioChange };
}

describe('PlanForm demo button', () => {
  it('fills the demo trip, enables demo mode and plans it', async () => {
    const { onSubmit, onScenarioChange } = renderForm();
    const button = screen.getByRole('button', { name: 'Load demo scenario' });
    expect(button).toHaveAttribute('aria-pressed', 'false');
    await userEvent.click(button);

    expect(onScenarioChange).toHaveBeenCalledWith('winter_storm');
    const req = onSubmit.mock.calls[0][0];
    expect(req).toMatchObject({
      scenario: 'winter_storm',
      load_weight_lb: 45000,
      interval_miles: 25,
    });
    const dep = new Date(req.departure_time);
    expect(dep.getMinutes()).toBe(0);
    expect(dep.getTime() - Date.now()).toBeGreaterThanOrEqual(2 * 3600_000 - 1000);
    expect(screen.getByLabelText('Origin')).toHaveValue('Denver, Colorado, United States');
    expect(screen.getByLabelText('Load weight (lb)')).toHaveValue(45000);
  });

  it('locks the locations and shows the pressed state in demo mode', () => {
    renderForm('winter_storm');
    expect(screen.getByRole('button', { name: 'Reload demo' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
    expect(screen.getByLabelText('Origin')).toBeDisabled();
    expect(screen.getByLabelText('Destination')).toBeDisabled();
    expect(screen.getByLabelText('Load weight (lb)')).toBeEnabled();
  });
});
