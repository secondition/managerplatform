import type {
  MetricDirection,
  TrafficMetricOut,
  WeekColumnOut,
} from '@/types/api';
import { api } from './client';

// `end` is the Monday (YYYY-MM-DD) of the newest week in the window; omit to
// let the server default to the current week. `count` = window size.
function windowQuery(end: string | null, count: number): string {
  const params = new URLSearchParams({ count: String(count) });
  if (end) params.set('end', end);
  return params.toString();
}

export function getWeekColumns(end: string | null, count: number): Promise<WeekColumnOut[]> {
  return api<WeekColumnOut[]>(`/traffic/weeks?${windowQuery(end, count)}`);
}

export function listMetrics(end: string | null, count: number): Promise<TrafficMetricOut[]> {
  return api<TrafficMetricOut[]>(`/traffic/metrics?${windowQuery(end, count)}`);
}

export interface CreateMetricInput {
  name: string;
  unit?: string | null;
  direction: MetricDirection;
  weekly_target?: number | null;
  north_star_target?: number | null;
  editor_ids?: number[];
  viewer_ids?: number[];
}

export function createMetric(input: CreateMetricInput): Promise<TrafficMetricOut[]> {
  return api<TrafficMetricOut[]>('/traffic/metrics', { method: 'POST', body: input });
}

export interface UpdateMetricInput {
  name?: string;
  unit?: string | null;
  direction?: MetricDirection;
  weekly_target?: number | null;
  north_star_target?: number | null;
  sort_order?: number;
  editor_ids?: number[];
  viewer_ids?: number[];
}

export function updateMetric(id: number, input: UpdateMetricInput): Promise<TrafficMetricOut[]> {
  return api<TrafficMetricOut[]>(`/traffic/metrics/${id}`, { method: 'PATCH', body: input });
}

export function deleteMetric(id: number): Promise<null> {
  return api<null>(`/traffic/metrics/${id}`, { method: 'DELETE' });
}

export interface UpsertValueInput {
  // status is computed server-side from value vs. weekly target — not sent by the client.
  value?: number | null;
  note?: string | null;
}

// `weekStart` is the Monday (YYYY-MM-DD) of the target week.
export function upsertMetricValue(
  assignmentId: number,
  weekStart: string,
  input: UpsertValueInput,
): Promise<TrafficMetricOut> {
  return api<TrafficMetricOut>(`/traffic/metric-assignments/${assignmentId}/values/${weekStart}`, {
    method: 'PATCH',
    body: input,
  });
}
