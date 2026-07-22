import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as dailyApi from '@/api/daily';
import type {
  CreateTaskInput,
  CreateProblemInput,
  UpdateProblemInput,
  UpdateTaskInput,
} from '@/api/daily';

// Query keys are scoped by date so switching days refetches cleanly.
const dailyKey = (date: string) => ['daily', date] as const;
const weekKey = (date: string) => ['daily-week', date] as const;
const rangeKey = (start: string, end: string) => ['daily-range', start, end] as const;

export function useDailyReport(date: string) {
  return useQuery({
    queryKey: dailyKey(date),
    queryFn: () => dailyApi.getDaily(date),
  });
}

export function useWeekSummary(date: string) {
  return useQuery({
    queryKey: weekKey(date),
    queryFn: () => dailyApi.getWeek(date),
  });
}

export function useDailyRange(start: string, end: string, enabled = true) {
  return useQuery({
    queryKey: rangeKey(start, end),
    queryFn: () => dailyApi.getDailyRange(start, end),
    enabled,
  });
}

// After any mutation, invalidate the day plus cached week/range summaries.
// `date` is the report date the mutation targets.
function useDailyInvalidate(date: string) {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: dailyKey(date) });
    qc.invalidateQueries({ queryKey: weekKey(date) });
    qc.invalidateQueries({ queryKey: ['daily-range'] });
  };
}

export function useCreateTask(date: string) {
  const invalidate = useDailyInvalidate(date);
  return useMutation({
    mutationFn: (input: CreateTaskInput) => dailyApi.createTask(input),
    onSuccess: invalidate,
  });
}

export function useSetTaskDone(date: string) {
  const invalidate = useDailyInvalidate(date);
  return useMutation({
    mutationFn: ({ id, isDone }: { id: number; isDone: boolean }) =>
      dailyApi.setTaskDone(id, isDone),
    onSuccess: invalidate,
  });
}

export function useUpdateTask(date: string) {
  const invalidate = useDailyInvalidate(date);
  return useMutation({
    mutationFn: ({ id, input }: { id: number; input: UpdateTaskInput }) =>
      dailyApi.updateTask(id, input),
    onSuccess: invalidate,
  });
}

export function useDeleteTask(date: string) {
  const invalidate = useDailyInvalidate(date);
  return useMutation({
    mutationFn: (id: number) => dailyApi.deleteTask(id),
    onSuccess: invalidate,
  });
}

export function useCreateProblem(date: string) {
  const invalidate = useDailyInvalidate(date);
  return useMutation({
    mutationFn: (input: CreateProblemInput) => dailyApi.createProblem(input),
    onSuccess: invalidate,
  });
}

export function useUpdateProblem(date: string) {
  const invalidate = useDailyInvalidate(date);
  return useMutation({
    mutationFn: ({ id, input }: { id: number; input: UpdateProblemInput }) =>
      dailyApi.updateProblem(id, input),
    onSuccess: invalidate,
  });
}

export function useDeleteProblem(date: string) {
  const invalidate = useDailyInvalidate(date);
  return useMutation({
    mutationFn: (id: number) => dailyApi.deleteProblem(id),
    onSuccess: invalidate,
  });
}
