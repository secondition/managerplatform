import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as trafficApi from '@/api/traffic';
import type { CreateMetricInput, UpdateMetricInput, UpsertValueInput } from '@/api/traffic';

// Window is identified by its newest-week anchor (Monday, or null = latest) + size.
export interface WindowKey {
  end: string | null;
  count: number;
}

const columnsKey = (w: WindowKey) => ['traffic-columns', w.end, w.count] as const;
const metricsKey = (w: WindowKey) => ['traffic-metrics', w.end, w.count] as const;

export function useWeekColumns(w: WindowKey) {
  return useQuery({
    queryKey: columnsKey(w),
    queryFn: () => trafficApi.getWeekColumns(w.end, w.count),
  });
}

export function useMetrics(w: WindowKey) {
  return useQuery({
    queryKey: metricsKey(w),
    queryFn: () => trafficApi.listMetrics(w.end, w.count),
  });
}

function useMetricsInvalidate() {
  const qc = useQueryClient();
  // Metrics change (create/update/value) affect every window, so invalidate the family.
  return () => qc.invalidateQueries({ queryKey: ['traffic-metrics'] });
}

export function useCreateMetric() {
  const invalidate = useMetricsInvalidate();
  return useMutation({
    mutationFn: (input: CreateMetricInput) => trafficApi.createMetric(input),
    onSuccess: invalidate,
  });
}

export function useUpdateMetric() {
  const invalidate = useMetricsInvalidate();
  return useMutation({
    mutationFn: ({ id, input }: { id: number; input: UpdateMetricInput }) =>
      trafficApi.updateMetric(id, input),
    onSuccess: invalidate,
  });
}

export function useDeleteMetric() {
  const invalidate = useMetricsInvalidate();
  return useMutation({
    mutationFn: (id: number) => trafficApi.deleteMetric(id),
    onSuccess: invalidate,
  });
}

export function useUpsertValue() {
  const invalidate = useMetricsInvalidate();
  return useMutation({
    mutationFn: ({
      assignmentId,
      weekStart,
      input,
    }: {
      assignmentId: number;
      weekStart: string;
      input: UpsertValueInput;
    }) => trafficApi.upsertMetricValue(assignmentId, weekStart, input),
    onSuccess: invalidate,
  });
}
