import type {
  KeyResultProgressOut,
  MonthlyReportSectionOut,
  MonthlyReportScoreOut,
  ObjectiveOut,
  OkrMonthOut,
  OkrReviewFullOut,
  OkrCommentOut,
} from '@/types/api';
import { api } from './client';

export function getOkrMonth(month: string): Promise<OkrMonthOut> {
  return api<OkrMonthOut>(`/okr?month=${encodeURIComponent(month)}`);
}

export interface KeyResultInput {
  title: string;
  progress?: number;
}

export interface CreateObjectiveInput {
  month: string;
  title: string;
  key_results?: KeyResultInput[];
}

export function createObjective(input: CreateObjectiveInput): Promise<ObjectiveOut> {
  return api<ObjectiveOut>('/okr/objectives', { method: 'POST', body: input });
}

export interface UpdateObjectiveInput {
  title?: string;
}

export function updateObjective(id: number, input: UpdateObjectiveInput): Promise<ObjectiveOut> {
  return api<ObjectiveOut>(`/okr/objectives/${id}`, { method: 'PATCH', body: input });
}

export function reorderObjectives(month: string, ids: number[]): Promise<OkrMonthOut> {
  return api<OkrMonthOut>(`/okr/objectives/reorder?month=${encodeURIComponent(month)}`, { method: 'POST', body: { ids } });
}

export function deleteObjective(id: number): Promise<null> {
  return api<null>(`/okr/objectives/${id}`, { method: 'DELETE' });
}

export function addKeyResult(objectiveId: number, input: KeyResultInput): Promise<ObjectiveOut> {
  return api<ObjectiveOut>(`/okr/objectives/${objectiveId}/key-results`, {
    method: 'POST',
    body: input,
  });
}

export interface UpdateKeyResultInput {
  title?: string;
  progress?: number;
}

export function updateKeyResult(krId: number, input: UpdateKeyResultInput): Promise<ObjectiveOut> {
  return api<ObjectiveOut>(`/okr/key-results/${krId}`, { method: 'PATCH', body: input });
}

export function reorderKeyResults(objectiveId: number, ids: number[]): Promise<ObjectiveOut> {
  return api<ObjectiveOut>(`/okr/objectives/${objectiveId}/key-results/reorder`, { method: 'POST', body: { ids } });
}

export function deleteKeyResult(krId: number): Promise<ObjectiveOut> {
  return api<ObjectiveOut>(`/okr/key-results/${krId}`, { method: 'DELETE' });
}

export interface CreateKeyResultProgressInput {
  note: string;
  progress_date: string;
}

export function listKeyResultProgress(krId: number): Promise<KeyResultProgressOut[]> {
  return api<KeyResultProgressOut[]>(`/okr/key-results/${krId}/progress`);
}

export function createKeyResultProgress(
  krId: number,
  input: CreateKeyResultProgressInput,
): Promise<KeyResultProgressOut> {
  return api<KeyResultProgressOut>(`/okr/key-results/${krId}/progress`, {
    method: 'POST',
    body: input,
  });
}

export type OkrCommentTarget = 'objective' | 'key-result';

function commentPath(target: OkrCommentTarget, targetId: number): string {
  return target === 'objective'
    ? `/okr/objectives/${targetId}/comments`
    : `/okr/key-results/${targetId}/comments`;
}

export function listOkrComments(
  target: OkrCommentTarget,
  targetId: number,
): Promise<OkrCommentOut[]> {
  return api<OkrCommentOut[]>(commentPath(target, targetId));
}

export function createOkrComment(
  target: OkrCommentTarget,
  targetId: number,
  content: string,
): Promise<OkrCommentOut> {
  return api<OkrCommentOut>(commentPath(target, targetId), {
    method: 'POST',
    body: { content },
  });
}

export function updateOkrComment(commentId: number, content: string): Promise<OkrCommentOut> {
  return api<OkrCommentOut>(`/okr/comments/${commentId}`, {
    method: 'PATCH',
    body: { content },
  });
}

export function deleteOkrComment(commentId: number): Promise<null> {
  return api<null>(`/okr/comments/${commentId}`, { method: 'DELETE' });
}

export function getReview(month: string): Promise<OkrReviewFullOut> {
  return api<OkrReviewFullOut>(`/okr/review?month=${encodeURIComponent(month)}`);
}

export function generateReview(month: string): Promise<OkrReviewFullOut> {
  return api<OkrReviewFullOut>(`/okr/review/generate?month=${encodeURIComponent(month)}`, {
    method: 'POST',
  });
}

export function getMonthlyReportScore(month: string): Promise<MonthlyReportScoreOut> {
  return api<MonthlyReportScoreOut>(
    `/okr/monthly-report/score?month=${encodeURIComponent(month)}`,
  );
}

export function generateMonthlyReportScore(month: string): Promise<MonthlyReportScoreOut> {
  return api<MonthlyReportScoreOut>(
    `/okr/monthly-report/score/generate?month=${encodeURIComponent(month)}`,
    { method: 'POST' },
  );
}

export interface UpdateSectionInput {
  title?: string;
  content_html?: string | null;
  content_json?: string | null;
}

export function updateReportSection(
  sectionId: number,
  input: UpdateSectionInput,
): Promise<MonthlyReportSectionOut> {
  return api<MonthlyReportSectionOut>(`/okr/monthly-report/sections/${sectionId}`, {
    method: 'PATCH',
    body: input,
  });
}
