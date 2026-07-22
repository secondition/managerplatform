import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as dailyApi from '@/api/daily';
import { getAiFeatureFlags } from '@/api/ai';
import type { DailySuggestionListOut } from '@/types/api';

const scoreKey = (date: string) => ['daily-score', date] as const;
const weeklyScoreKey = (date: string) => ['weekly-score', date] as const;
const suggestionKey = (date: string) => ['daily-suggestions', date] as const;

// Shared AI feature toggles — gate the daily score / suggestion / OKR review
// panels. Cached briefly so an admin's toggle reflects on the next navigation.
export function useAiFeatureFlags() {
  return useQuery({
    queryKey: ['ai-feature-flags'],
    queryFn: getAiFeatureFlags,
    staleTime: 30_000,
  });
}

export function useDailyScore(date: string) {
  return useQuery({
    queryKey: scoreKey(date),
    queryFn: () => dailyApi.getDailyScore(date),
  });
}

export function useGenerateDailyScore(date: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => dailyApi.generateDailyScore(date),
    onSuccess: (data) => qc.setQueryData(scoreKey(date), data),
  });
}

export function useWeeklyScore(date: string) {
  return useQuery({
    queryKey: weeklyScoreKey(date),
    queryFn: () => dailyApi.getWeeklyScore(date),
  });
}

export function useGenerateWeeklyScore(date: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => dailyApi.generateWeeklyScore(date),
    onSuccess: (data) => qc.setQueryData(weeklyScoreKey(date), data),
  });
}

export function useSuggestions(date: string) {
  return useQuery({
    queryKey: suggestionKey(date),
    queryFn: () => dailyApi.getSuggestions(date),
  });
}

export function useGenerateSuggestions(date: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (realtimeSupplement?: string) =>
      dailyApi.generateSuggestions(date, realtimeSupplement),
    onSuccess: (data) => qc.setQueryData(suggestionKey(date), data),
  });
}

export function useAcceptSuggestion(date: string) {
  const qc = useQueryClient();
  const removeSuggestion = (id: number) => {
    qc.setQueryData<DailySuggestionListOut>(suggestionKey(date), (current) => {
      if (!current) return current;
      const items = current.items.filter((item) => item.id !== id);
      return { ...current, status: items.length > 0 ? current.status : 'empty', items };
    });
  };
  return useMutation({
    mutationFn: (id: number) => dailyApi.acceptSuggestion(id),
    onSuccess: (_data, id) => {
      removeSuggestion(id);
      qc.invalidateQueries({ queryKey: suggestionKey(date) });
      qc.invalidateQueries({ queryKey: ['daily', date] });
      qc.invalidateQueries({ queryKey: ['daily-week', date] });
    },
  });
}

export function useRejectSuggestion(date: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => dailyApi.rejectSuggestion(id),
    onSuccess: (_data, id) => {
      qc.setQueryData<DailySuggestionListOut>(suggestionKey(date), (current) => {
        if (!current) return current;
        const items = current.items.filter((item) => item.id !== id);
        return { ...current, status: items.length > 0 ? current.status : 'empty', items };
      });
      qc.invalidateQueries({ queryKey: suggestionKey(date) });
    },
  });
}
