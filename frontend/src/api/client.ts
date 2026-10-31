import type {
  ApiErrorBody,
  HeatmapRequest,
  HeatmapResponse,
  Place,
  PlanRequest,
  PlanResponse,
} from './types';

const API_URL = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '');

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly code: string,
    public readonly details?: unknown,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init.headers ?? {}) },
    });
  } catch (err) {
    if ((err as Error).name === 'AbortError') throw err;
    throw new ApiError('Cannot reach the server. Check your connection.', 0, 'network_error');
  }
  const text = await resp.text();
  let body: unknown = null;
  try {
    body = text ? JSON.parse(text) : null;
  } catch {
    // Non-JSON error page (e.g. gateway timeout)
  }
  if (!resp.ok) {
    const err = (body as ApiErrorBody | null)?.error;
    throw new ApiError(
      err?.message ?? `Request failed (HTTP ${resp.status})`,
      resp.status,
      err?.code ?? 'http_error',
      err?.details,
    );
  }
  return body as T;
}

export const api = {
  geocode(q: string, signal?: AbortSignal): Promise<{ results: Place[] }> {
    return request(`/api/geocode?q=${encodeURIComponent(q)}`, { signal });
  },
  plan(body: PlanRequest): Promise<PlanResponse> {
    return request('/api/plan', { method: 'POST', body: JSON.stringify(body) });
  },
  heatmap(body: HeatmapRequest, signal?: AbortSignal): Promise<HeatmapResponse> {
    return request('/api/heatmap', { method: 'POST', body: JSON.stringify(body), signal });
  },
};
