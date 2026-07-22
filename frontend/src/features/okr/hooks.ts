import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as okrApi from '@/api/okr';
import type {
  CreateObjectiveInput,
  CreateKeyResultProgressInput,
  KeyResultInput,
  UpdateKeyResultInput,
  UpdateObjectiveInput,
  UpdateSectionInput,
  OkrCommentTarget,
} from '@/api/okr';

const monthKey = (month: string) => ['okr-month', month] as const;

export function useOkrMonth(month: string) {
  return useQuery({
    queryKey: monthKey(month),
    queryFn: () => okrApi.getOkrMonth(month),
  });
}

function useMonthInvalidate(month: string) {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: monthKey(month) });
}

export function useCreateObjective(month: string) {
  const invalidate = useMonthInvalidate(month);
  return useMutation({
    mutationFn: (input: CreateObjectiveInput) => okrApi.createObjective(input),
    onSuccess: invalidate,
  });
}

export function useUpdateObjective(month: string) {
  const invalidate = useMonthInvalidate(month);
  return useMutation({
    mutationFn: ({ id, input }: { id: number; input: UpdateObjectiveInput }) =>
      okrApi.updateObjective(id, input),
    onSuccess: invalidate,
  });
}

export function useReorderObjectives(month: string) {
  const invalidate = useMonthInvalidate(month);
  return useMutation({
    mutationFn: (ids: number[]) => okrApi.reorderObjectives(month, ids),
    onSuccess: invalidate,
  });
}

export function useDeleteObjective(month: string) {
  const invalidate = useMonthInvalidate(month);
  return useMutation({
    mutationFn: (id: number) => okrApi.deleteObjective(id),
    onSuccess: invalidate,
  });
}

export function useAddKeyResult(month: string) {
  const invalidate = useMonthInvalidate(month);
  return useMutation({
    mutationFn: ({ objectiveId, input }: { objectiveId: number; input: KeyResultInput }) =>
      okrApi.addKeyResult(objectiveId, input),
    onSuccess: invalidate,
  });
}

export function useUpdateKeyResult(month: string) {
  const invalidate = useMonthInvalidate(month);
  return useMutation({
    mutationFn: ({ krId, input }: { krId: number; input: UpdateKeyResultInput }) =>
      okrApi.updateKeyResult(krId, input),
    onSuccess: invalidate,
  });
}

export function useReorderKeyResults(month: string) {
  const invalidate = useMonthInvalidate(month);
  return useMutation({
    mutationFn: ({ objectiveId, ids }: { objectiveId: number; ids: number[] }) => okrApi.reorderKeyResults(objectiveId, ids),
    onSuccess: invalidate,
  });
}

export function useDeleteKeyResult(month: string) {
  const invalidate = useMonthInvalidate(month);
  return useMutation({
    mutationFn: (krId: number) => okrApi.deleteKeyResult(krId),
    onSuccess: invalidate,
  });
}

export function useCreateKeyResultProgress(month: string) {
  const invalidate = useMonthInvalidate(month);
  return useMutation({
    mutationFn: ({ krId, input }: { krId: number; input: CreateKeyResultProgressInput }) =>
      okrApi.createKeyResultProgress(krId, input),
    onSuccess: invalidate,
  });
}

const commentsKey = (target: OkrCommentTarget, targetId: number) =>
  ['okr-comments', target, targetId] as const;

export function useOkrComments(target: OkrCommentTarget, targetId: number) {
  return useQuery({
    queryKey: commentsKey(target, targetId),
    queryFn: () => okrApi.listOkrComments(target, targetId),
  });
}

export function useCreateOkrComment(month: string, target: OkrCommentTarget, targetId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (content: string) => okrApi.createOkrComment(target, targetId, content),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: commentsKey(target, targetId) });
      qc.invalidateQueries({ queryKey: monthKey(month) });
    },
  });
}

export function useUpdateOkrComment(target: OkrCommentTarget, targetId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ commentId, content }: { commentId: number; content: string }) =>
      okrApi.updateOkrComment(commentId, content),
    onSuccess: () => qc.invalidateQueries({ queryKey: commentsKey(target, targetId) }),
  });
}

export function useDeleteOkrComment(month: string, target: OkrCommentTarget, targetId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (commentId: number) => okrApi.deleteOkrComment(commentId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: commentsKey(target, targetId) });
      qc.invalidateQueries({ queryKey: monthKey(month) });
    },
  });
}

export function useUpdateReportSection(month: string) {
  const invalidate = useMonthInvalidate(month);
  return useMutation({
    mutationFn: ({ sectionId, input }: { sectionId: number; input: UpdateSectionInput }) =>
      okrApi.updateReportSection(sectionId, input),
    onSuccess: invalidate,
  });
}

const reviewKey = (month: string) => ['okr-review', month] as const;

export function useOkrReview(month: string) {
  return useQuery({
    queryKey: reviewKey(month),
    queryFn: () => okrApi.getReview(month),
  });
}

export function useGenerateOkrReview(month: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => okrApi.generateReview(month),
    onSuccess: (data) => {
      qc.setQueryData(reviewKey(month), data);
      // Refresh the lightweight review summary embedded in the month payload.
      qc.invalidateQueries({ queryKey: monthKey(month) });
    },
  });
}

const monthlyReportScoreKey = (month: string) => ['monthly-report-score', month] as const;

export function useMonthlyReportScore(month: string) {
  return useQuery({
    queryKey: monthlyReportScoreKey(month),
    queryFn: () => okrApi.getMonthlyReportScore(month),
  });
}

export function useGenerateMonthlyReportScore(month: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => okrApi.generateMonthlyReportScore(month),
    onSuccess: (data) => qc.setQueryData(monthlyReportScoreKey(month), data),
  });
}
