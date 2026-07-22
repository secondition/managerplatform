import { api } from './client';
import type { GroupOut } from './admin';

// 人员组共享变量池 —— 全公司共享，凭 feature:group 访问（owner 也按权限行判断）。
// 端点独立于后台管理（/groups），成员消费仍走 /users/groups。

export interface GroupInput {
  name: string;
  description?: string | null;
  sort_order?: number;
  member_ids?: number[];
}

export interface GroupImportSource {
  id: number;
  name: string;
}

export function listGroups(): Promise<GroupOut[]> {
  return api<GroupOut[]>('/groups');
}

export function listGroupImportSources(): Promise<GroupImportSource[]> {
  return api<GroupImportSource[]>('/groups/import-sources');
}

export function createGroup(input: GroupInput): Promise<GroupOut> {
  return api<GroupOut>('/groups', { method: 'POST', body: input });
}

export function updateGroup(
  id: number,
  input: Partial<Omit<GroupInput, 'member_ids'>>,
): Promise<GroupOut> {
  return api<GroupOut>(`/groups/${id}`, { method: 'PATCH', body: input });
}

export function setGroupMembers(id: number, memberIds: number[]): Promise<GroupOut> {
  return api<GroupOut>(`/groups/${id}/members`, {
    method: 'POST',
    body: { member_ids: memberIds },
  });
}

export function createGroupFromDepartment(
  departmentId: number,
  name?: string | null,
): Promise<GroupOut> {
  return api<GroupOut>('/groups/from-department', {
    method: 'POST',
    body: { department_id: departmentId, name: name ?? null },
  });
}

export function deleteGroup(id: number): Promise<null> {
  return api<null>(`/groups/${id}`, { method: 'DELETE' });
}
