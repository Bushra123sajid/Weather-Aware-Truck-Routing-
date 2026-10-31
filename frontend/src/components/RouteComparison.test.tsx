import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';
import { route } from '../test/fixtures';
import { RouteComparison } from './RouteComparison';

describe('RouteComparison', () => {
  const routes = [
    route('r1', 2, { severe_miles: 18, max_risk: 4 }),
    route('r2', 1, { severe_miles: 0 }),
    route('r3', 3, { severe_miles: 25, no_travel_miles: 3, max_risk: 5 }),
  ];

  it('lists routes best-first with a recommended badge', () => {
    render(<RouteComparison routes={routes} selectedId="r2" onSelect={() => {}} />);
    const rows = screen.getAllByRole('row').slice(1);
    expect(rows.map((r) => within(r).getByRole('rowheader').textContent)).toEqual([
      'Route 2Recommended',
      'Route 1',
      'Route 3',
    ]);
    expect(rows[0]).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('columnheader', { name: 'No Travel' })).toBeInTheDocument();
    expect(within(rows[2]).getByLabelText('Risk: No Travel')).toBeInTheDocument();
  });

  it('selects a route on click and keyboard', async () => {
    const onSelect = vi.fn();
    render(<RouteComparison routes={routes} selectedId="r2" onSelect={onSelect} />);
    const row = screen.getByRole('rowheader', { name: /Route 3/ }).closest('tr')!;
    await userEvent.click(row);
    expect(onSelect).toHaveBeenCalledWith('r3');
    row.focus();
    await userEvent.keyboard('{Enter}');
    expect(onSelect).toHaveBeenCalledTimes(2);
  });
});
