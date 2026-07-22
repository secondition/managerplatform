import type {
  DailySubscriptionCandidateOut,
  DailySubscriptionOut,
  OkrSubscriptionCandidateOut,
  OkrSubscriptionOut,
  SubscribedDailyReportOut,
  SubscribedOkrMonthOut,
} from '@/types/api';
import { api } from './client';

export function listDailySubscriptions(): Promise<DailySubscriptionOut[]> {
  return api<DailySubscriptionOut[]>('/subscriptions/daily');
}

export function listDailySubscriptionCandidates(q?: string): Promise<DailySubscriptionCandidateOut[]> {
  const query = q && q.trim() ? `?q=${encodeURIComponent(q.trim())}` : '';
  return api<DailySubscriptionCandidateOut[]>(`/subscriptions/daily/candidates${query}`);
}

export function subscribeDailyUser(userId: number): Promise<DailySubscriptionOut> {
  return api<DailySubscriptionOut>(`/subscriptions/daily/${userId}`, { method: 'POST' });
}

export function unsubscribeDailyUser(userId: number): Promise<null> {
  return api<null>(`/subscriptions/daily/${userId}`, { method: 'DELETE' });
}

export function getSubscribedDailyReport(userId: number, date: string): Promise<SubscribedDailyReportOut> {
  return api<SubscribedDailyReportOut>(`/subscriptions/daily/${userId}/report?date=${date}`);
}

// ---- OKR subscriptions ----------------------------------------------------

export function listOkrSubscriptions(): Promise<OkrSubscriptionOut[]> {
  return api<OkrSubscriptionOut[]>('/subscriptions/okr');
}

export function listOkrSubscriptionCandidates(q?: string): Promise<OkrSubscriptionCandidateOut[]> {
  const query = q && q.trim() ? `?q=${encodeURIComponent(q.trim())}` : '';
  return api<OkrSubscriptionCandidateOut[]>(`/subscriptions/okr/candidates${query}`);
}

export function subscribeOkrUser(userId: number): Promise<OkrSubscriptionOut> {
  return api<OkrSubscriptionOut>(`/subscriptions/okr/${userId}`, { method: 'POST' });
}

export function unsubscribeOkrUser(userId: number): Promise<null> {
  return api<null>(`/subscriptions/okr/${userId}`, { method: 'DELETE' });
}

export function getSubscribedOkrMonth(userId: number, month: string): Promise<SubscribedOkrMonthOut> {
  return api<SubscribedOkrMonthOut>(`/subscriptions/okr/${userId}/report?month=${encodeURIComponent(month)}`);
}
