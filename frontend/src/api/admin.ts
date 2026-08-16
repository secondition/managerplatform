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

export interface AdminAgentOut {
  id: number;
  agent_key: string;
  name: string;
  description: string;
  avatar_url: string | null;
  implementation_type: string;
  enabled: boolean;
  sort_order: number;
  direct_user_count: number;
  group_count: number;
  effective_user_count: number;
  chat_member_count: number;
  non_chat_member_count: number;
}

export interface AgentAccessUserOut {
  id: number;
  name: string;
  avatar_url: string | null;
  status: string;
}

export interface AgentAccessGroupOut {
  id: number;
  name: string;
  member_count: number;
}

export interface AgentAccessOut {
  agent: AdminAgentOut;
  users: AgentAccessUserOut[];
  groups: AgentAccessGroupOut[];
}

export interface AgentFeishuChatConfigOut {
  target_chat_id: string;
  target_chat_name: string;
  agent_sender_id: string;
  agent_mention_id: string;
  agent_display_name: string;
  complete: boolean;
}

export type AgentFeishuChatConfigInput = Omit<AgentFeishuChatConfigOut, 'complete'>;

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

// ---- Agent access ----

export function listAdminAgents(): Promise<AdminAgentOut[]> {
  return api<AdminAgentOut[]>('/admin/agents');
}

export function getAgentAccess(agentId: number): Promise<AgentAccessOut> {
  return api<AgentAccessOut>(`/admin/agents/${agentId}/access`);
}

export interface AgentPresentationInput {
  name: string;
  description: string;
}

export function updateAgentPresentation(
  agentId: number,
  input: AgentPresentationInput,
): Promise<AdminAgentOut> {
  return api<AdminAgentOut>(`/admin/agents/${agentId}`, {
    method: 'PATCH',
    body: input,
  });
}

export function uploadAgentAvatar(agentId: number, file: File): Promise<AdminAgentOut> {
  const form = new FormData();
  form.append('avatar', file);
  return api<AdminAgentOut>(`/admin/agents/${agentId}/avatar`, {
    method: 'POST',
    body: form,
  });
}

export function removeAgentAvatar(agentId: number): Promise<AdminAgentOut> {
  return api<AdminAgentOut>(`/admin/agents/${agentId}/avatar`, { method: 'DELETE' });
}

export function getAgentFeishuChatConfig(agentId: number): Promise<AgentFeishuChatConfigOut> {
  return api<AgentFeishuChatConfigOut>(`/admin/agents/${agentId}/feishu-chat-config`);
}

export function updateAgentFeishuChatConfig(
  agentId: number,
  input: AgentFeishuChatConfigInput,
): Promise<AgentFeishuChatConfigOut> {
  return api<AgentFeishuChatConfigOut>(`/admin/agents/${agentId}/feishu-chat-config`, {
    method: 'PATCH',
    body: input,
  });
}

export function replaceAgentAccess(
  agentId: number,
  input: { user_ids: number[]; group_ids: number[] },
): Promise<AgentAccessOut> {
  return api<AgentAccessOut>(`/admin/agents/${agentId}/access`, {
    method: 'PUT',
    body: input,
  });
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

// ---- Notifications ----

export interface NotificationChannelRuleOut {
  notification_type: string;
  label: string;
  description: string;
  in_app_enabled: boolean;
  feishu_enabled: boolean;
  feishu_available: boolean;
}

export interface NotificationDeliverySummaryOut {
  pending: number;
  retry: number;
  sent: number;
  failed: number;
  cancelled: number;
  latest_errors: string[];
}

export function listNotificationSettings(): Promise<NotificationChannelRuleOut[]> {
  return api<NotificationChannelRuleOut[]>('/admin/notification-settings');
}

export function updateNotificationSetting(
  type: string,
  input: Partial<Pick<NotificationChannelRuleOut, 'in_app_enabled' | 'feishu_enabled'>>,
): Promise<NotificationChannelRuleOut> {
  return api<NotificationChannelRuleOut>(`/admin/notification-settings/${type}`, {
    method: 'PATCH',
    body: input,
  });
}

export function getNotificationDeliverySummary(): Promise<NotificationDeliverySummaryOut> {
  return api<NotificationDeliverySummaryOut>('/admin/notification-settings/delivery-summary');
}

export function testFeishuNotification(userId?: number): Promise<{ ok: boolean; message: string }> {
  return api<{ ok: boolean; message: string }>('/admin/notification-settings/test-feishu', {
    method: 'POST',
    body: { user_id: userId ?? null },
  });
}

// 人员组 (people groups) 已迁至独立模块 api/groups.ts（feature:group 门控）。
// GroupOut 仍在此定义供两处复用。


