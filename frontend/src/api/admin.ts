import type { Role } from '@/types/api';
import { api } from './client';

export interface EmployeeOut {
  id: number;
  name: string;
  email: string | null;
  avatar_url: string | null;
  role: Role;
  department_id: number | null;
  status: string;
  last_login_at: string | null;
  sync_source: string;
  last_synced_at: string | null;
  disabled_reason: string | null;
  permissions: string[];
}

export interface DepartmentOut {
  id: number;
  name: string;
  parent_id: number | null;
  feishu_department_id: string | null;
  sort_order: number;
  last_synced_at: string | null;
}

export interface GroupOut {
  id: number;
  name: string;
  description: string | null;
  source: string;
  sort_order: number;
  member_ids: number[];
}

// ---- Employees ----

export interface EmployeeUpdateInput {
  name?: string;
  email?: string | null;
  department_id?: number | null;
}

export function listEmployees(): Promise<EmployeeOut[]> {
  return api<EmployeeOut[]>('/admin/employees');
}

export function updateEmployee(id: number, input: EmployeeUpdateInput): Promise<EmployeeOut> {
  return api<EmployeeOut>(`/admin/employees/${id}`, { method: 'PATCH', body: input });
}

export function setEmployeePermissions(id: number, permissions: string[]): Promise<EmployeeOut> {
  return api<EmployeeOut>(`/admin/employees/${id}/permissions`, {
    method: 'POST',
    body: { permissions },
  });
}

export function setEmployeeStatus(id: number, status: 'active' | 'disabled'): Promise<EmployeeOut> {
  return api<EmployeeOut>(`/admin/employees/${id}/status`, { method: 'POST', body: { status } });
}

export function deleteEmployee(id: number): Promise<null> {
  return api<null>(`/admin/employees/${id}`, { method: 'DELETE' });
}

export interface ContactSyncOut {
  created: number;
  updated: number;
  disabled: number;
  skipped: number;
  status: string;
  started_at: string | null;
  finished_at: string | null;
  error_message: string | null;
}

export interface ContactSyncLogOut {
  id: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  created_count: number;
  updated_count: number;
  disabled_count: number;
  skipped_count: number;
  error_message: string | null;
}

export function syncFeishuContacts(): Promise<ContactSyncOut> {
  return api<ContactSyncOut>('/admin/feishu/sync-contacts', { method: 'POST' });
}

export function listFeishuContactSyncLogs(): Promise<ContactSyncLogOut[]> {
  return api<ContactSyncLogOut[]>('/admin/feishu/sync-logs');
}

// ---- Departments ----

export interface DepartmentInput {
  name: string;
  parent_id?: number | null;
  sort_order?: number;
}

export function listDepartments(): Promise<DepartmentOut[]> {
  return api<DepartmentOut[]>('/admin/departments');
}

export function createDepartment(input: DepartmentInput): Promise<DepartmentOut> {
  return api<DepartmentOut>('/admin/departments', { method: 'POST', body: input });
}

export function updateDepartment(id: number, input: Partial<DepartmentInput>): Promise<DepartmentOut> {
  return api<DepartmentOut>(`/admin/departments/${id}`, { method: 'PATCH', body: input });
}

export function deleteDepartment(id: number): Promise<null> {
  return api<null>(`/admin/departments/${id}`, { method: 'DELETE' });
}

// 人员组 (people groups) 已迁至独立模块 api/groups.ts（feature:group 门控）。
// GroupOut 仍在此定义供两处复用。


