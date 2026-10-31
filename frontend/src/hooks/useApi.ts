import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import type { Place, PlanRequest, PlanResponse } from '../api/types';

/** Autocomplete suggestions; the caller passes an already-debounced query. */
export function useGeocode(query: string) {
  const q = query.trim();
  return useQuery<Place[], Error>({
    queryKey: ['geocode', q.toLowerCase()],
    queryFn: ({ signal }) => api.geocode(q, signal).then((r) => r.results),
    enabled: q.length >= 3,
    staleTime: 60 * 60_000,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

export function usePlan() {
  return useMutation({ mutationFn: (body: PlanRequest) => api.plan(body) });
}

/**
 * Corridor heatmap for a plan: fetched ONCE per plan (all 49 hours at once).
 * Moving the slider never changes the query key, so it never refetches.
 */
export function useHeatmap(plan: PlanResponse | undefined) {
  return useQuery({
    queryKey: ['heatmap', plan?.plan_id],
    queryFn: ({ signal }) =>
      api.heatmap(
        {
          polylines: plan!.routes.map((r) => r.geometry),
          load_weight_lb: plan!.load_weight_lb,
          start_time: plan!.departure_time,
          scenario: plan!.demo ? plan!.scenario : null,
        },
        signal,
      ),
    enabled: Boolean(plan),
    staleTime: 30 * 60_000,
    gcTime: 60 * 60_000,
    retry: 1,
  });
}
