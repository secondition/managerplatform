import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as subscriptionApi from '@/api/subscriptions';

const dailySubscriptionsKey = ['subscriptions', 'daily'] as const;
const dailyCandidatesKey = (q: string) => ['subscriptions', 'daily-candidates', q] as const;
const subscribedReportKey = (userId: number | null, date: string) =>
  ['subscriptions', 'daily-report', userId, date] as const;

export function useDailySubscriptions() {
  return useQuery({
    queryKey: dailySubscriptionsKey,
    queryFn: subscriptionApi.listDailySubscriptions,
  });
}

export function useDailySubscriptionCandidates(q: string) {
  return useQuery({
    queryKey: dailyCandidatesKey(q),
    queryFn: () => subscriptionApi.listDailySubscriptionCandidates(q),
  });
}

export function useSubscribeDaily() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: subscriptionApi.subscribeDailyUser,
    onSuccess: () => {
      // Subscriptions are unified (daily + OKR), so refresh both lists, both
      // candidate sets, and the profile subscription state together.
      qc.invalidateQueries({ queryKey: ['subscriptions'] });
      qc.invalidateQueries({ queryKey: ['people'] });
    },
  });
}

export function useUnsubscribeDaily() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: subscriptionApi.unsubscribeDailyUser,
    onSuccess: (_, userId) => {
      qc.invalidateQueries({ queryKey: ['subscriptions'] });
      qc.invalidateQueries({ queryKey: ['people'] });
      qc.removeQueries({ queryKey: ['subscriptions', 'daily-report', userId] });
      qc.removeQueries({ queryKey: ['subscriptions', 'okr-report', userId] });
    },
  });
}

export function useSubscribedDailyReport(userId: number | null, date: string) {
  return useQuery({
    queryKey: subscribedReportKey(userId, date),
    queryFn: () => subscriptionApi.getSubscribedDailyReport(userId as number, date),
    enabled: userId !== null,
  });
}

// ---- OKR subscriptions -----------------------------------------------------

const okrSubscriptionsKey = ['subscriptions', 'okr'] as const;
const okrCandidatesKey = (q: string) => ['subscriptions', 'okr-candidates', q] as const;
const subscribedOkrKey = (userId: number | null, month: string) =>
  ['subscriptions', 'okr-report', userId, month] as const;

export function useOkrSubscriptions() {
  return useQuery({
    queryKey: okrSubscriptionsKey,
    queryFn: subscriptionApi.listOkrSubscriptions,
  });
}

export function useOkrSubscriptionCandidates(q: string) {
  return useQuery({
    queryKey: okrCandidatesKey(q),
    queryFn: () => subscriptionApi.listOkrSubscriptionCandidates(q),
  });
}

export function useSubscribeOkr() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: subscriptionApi.subscribeOkrUser,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['subscriptions'] });
      qc.invalidateQueries({ queryKey: ['people'] });
    },
  });
}

export function useUnsubscribeOkr() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: subscriptionApi.unsubscribeOkrUser,
    onSuccess: (_, userId) => {
      qc.invalidateQueries({ queryKey: ['subscriptions'] });
      qc.invalidateQueries({ queryKey: ['people'] });
      qc.removeQueries({ queryKey: ['subscriptions', 'daily-report', userId] });
      qc.removeQueries({ queryKey: ['subscriptions', 'okr-report', userId] });
    },
  });
}

export function useSubscribedOkrMonth(userId: number | null, month: string) {
  return useQuery({
    queryKey: subscribedOkrKey(userId, month),
    queryFn: () => subscriptionApi.getSubscribedOkrMonth(userId as number, month),
    enabled: userId !== null,
  });
}
