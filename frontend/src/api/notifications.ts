import { api } from './client';

export interface NotificationOut {
  id: number;
  type: string;
  title: string;
  body: string;
  action_url: string | null;
  entity_type: string | null;
  entity_id: number | null;
  metadata: Record<string, unknown> | unknown[] | null;
  read_at: string | null;
  created_at: string;
}

export interface NotificationPageOut {
  items: NotificationOut[];
  next_cursor: number | null;
}

export function listNotifications(cursor?: number): Promise<NotificationPageOut> {
  const params = new URLSearchParams({ limit: '30' });
  if (cursor) params.set('cursor', String(cursor));
  return api<NotificationPageOut>(`/notifications?${params}`);
}

export function getUnreadCount(): Promise<{ count: number }> {
  return api<{ count: number }>('/notifications/unread-count');
}

export function markNotificationRead(id: number): Promise<NotificationOut> {
  return api<NotificationOut>(`/notifications/${id}/read`, { method: 'POST' });
}

export function markAllNotificationsRead(): Promise<{ count: number }> {
  return api<{ count: number }>('/notifications/read-all', { method: 'POST' });
}
