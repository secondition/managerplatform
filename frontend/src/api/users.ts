import type { GroupBrief, UserBrief } from '@/types/api';
import { api } from './client';

// Directory used by collaborator / dispatch / metric-member pickers.
export function listUsers(q?: string): Promise<UserBrief[]> {
  const query = q && q.trim() ? `?q=${encodeURIComponent(q.trim())}` : '';
  return api<UserBrief[]>(`/users${query}`);
}

// 人员组目录：选择器选组后展开成 member_ids。
export function listUserGroups(): Promise<GroupBrief[]> {
  return api<GroupBrief[]>('/users/groups');
}
