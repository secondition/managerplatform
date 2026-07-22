import type {
  DailyReportOut,
  DailyRangeDayOut,
  DailyScoreOut,
  DailySuggestionListOut,
  DailySuggestionOut,
  DailyTaskOut,
  ProblemSolutionOut,
  WeeklyScoreOut,
  WeekDayOut,
} from '@/types/api';
import { api } from './client';

export function getDaily(date: string): Promise<DailyReportOut> {
  return api<DailyReportOut>(`/daily?date=${date}`);
}

export function getDailyRange(start: string, end: string): Promise<DailyRangeDayOut[]> {
  return api<DailyRangeDayOut[]>(`/daily/range?start=${start}&end=${end}`);
}

export function getWeek(date: string): Promise<WeekDayOut[]> {
  return api<WeekDayOut[]>(`/daily/week?date=${date}`);
}

export interface CreateTaskInput {
  date: string;
  task_time: string; // "HH:MM:SS"
  content: string;
  note?: string | null;
  is_private?: boolean;
  repeat_rule?: 'none' | 'daily' | 'weekly';
  collaborator_ids?: number[];
  // 派发目标（可多人；选人员组时前端展开成成员）。空=不派发。
  assigned_to_ids?: number[];
}

export function createTask(input: CreateTaskInput): Promise<DailyTaskOut> {
  return api<DailyTaskOut>('/daily/tasks', { method: 'POST', body: input });
}

export interface UpdateTaskInput {
  task_time?: string;
  content?: string;
  note?: string | null;
  is_private?: boolean;
  sort_order?: number;
  repeat_rule?: 'none' | 'daily' | 'weekly';
  collaborator_ids?: number[];
  assigned_to_ids?: number[];
}

export function updateTask(id: number, input: UpdateTaskInput): Promise<DailyTaskOut> {
  return api<DailyTaskOut>(`/daily/tasks/${id}`, { method: 'PATCH', body: input });
}

export function deleteTask(id: number): Promise<null> {
  return api<null>(`/daily/tasks/${id}`, { method: 'DELETE' });
}

export function setTaskDone(id: number, isDone: boolean): Promise<DailyTaskOut> {
  return api<DailyTaskOut>(`/daily/tasks/${id}/done`, {
    method: 'POST',
    body: { is_done: isDone },
  });
}

export interface CreateProblemInput {
  date: string;
  problem_text: string;
  solution_html?: string;
  solution_json?: Record<string, unknown> | unknown[] | null;
}

export function createProblem(input: CreateProblemInput): Promise<ProblemSolutionOut> {
  return api<ProblemSolutionOut>('/daily/problems', { method: 'POST', body: input });
}

export interface UpdateProblemInput {
  problem_text?: string;
  solution_html?: string;
  solution_json?: Record<string, unknown> | unknown[] | null;
  sort_order?: number;
}

export function updateProblem(id: number, input: UpdateProblemInput): Promise<ProblemSolutionOut> {
  return api<ProblemSolutionOut>(`/daily/problems/${id}`, { method: 'PATCH', body: input });
}

export function deleteProblem(id: number): Promise<null> {
  return api<null>(`/daily/problems/${id}`, { method: 'DELETE' });
}

// ---- AI: daily score + suggestions ----

export function getDailyScore(date: string): Promise<DailyScoreOut> {
  return api<DailyScoreOut>(`/daily/scores?date=${date}`);
}

export function generateDailyScore(date: string): Promise<DailyScoreOut> {
  return api<DailyScoreOut>(`/daily/scores/generate?date=${date}`, { method: 'POST' });
}

export function getWeeklyScore(date: string): Promise<WeeklyScoreOut> {
  return api<WeeklyScoreOut>(`/daily/weekly-score?date=${date}`);
}

export function generateWeeklyScore(date: string): Promise<WeeklyScoreOut> {
  return api<WeeklyScoreOut>(`/daily/weekly-score/generate?date=${date}`, { method: 'POST' });
}

export function getSuggestions(date: string): Promise<DailySuggestionListOut> {
  return api<DailySuggestionListOut>(`/daily/suggestions?date=${date}`);
}

export function generateSuggestions(
  date: string,
  realtimeSupplement = '',
): Promise<DailySuggestionListOut> {
  return api<DailySuggestionListOut>(`/daily/suggestions/generate?date=${date}`, {
    method: 'POST',
    body: { realtime_supplement: realtimeSupplement },
  });
}

export function acceptSuggestion(id: number): Promise<DailySuggestionOut> {
  return api<DailySuggestionOut>(`/daily/suggestions/${id}/accept`, { method: 'POST' });
}

export function rejectSuggestion(id: number): Promise<null> {
  return api<null>(`/daily/suggestions/${id}/reject`, { method: 'POST' });
}
