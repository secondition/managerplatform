import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as adminApi from '@/api/admin';
import { getMe } from '@/api/auth';
import { useAuthStore } from '@/stores/authStore';

const employeesKey = ['admin-employees'] as const;
const departmentsKey = ['admin-departments'] as const;
const contactSyncLogsKey = ['admin-contact-sync-logs'] as const;
const notificationSettingsKey = ['admin-notification-settings'] as const;
const notificationDeliverySummaryKey = ['admin-notification-delivery-summary'] as const;
const adminAgentsKey = ['admin-agents'] as const;

function agentAccessKey(agentId: number) {
  return ['admin-agent-access', agentId] as const;
}

function agentFeishuChatConfigKey(agentId: number) {
  return ['admin-agent-feishu-chat-config', agentId] as const;
}

function useSyncAgentPresentation() {
  const queryClient = useQueryClient();
  return (agent: adminApi.AdminAgentOut) => {
    queryClient.setQueryData<adminApi.AdminAgentOut[]>(adminAgentsKey, (current) => (
      current?.map((item) => (item.id === agent.id ? agent : item))
    ));
    queryClient.setQueryData<adminApi.AgentAccessOut>(agentAccessKey(agent.id), (current) => (
      current ? { ...current, agent } : current
    ));
    queryClient.invalidateQueries({ queryKey: ['chat-agents'] });
  };
}

// ---- Employees ----

export function useEmployees() {
  return useQuery({ queryKey: employeesKey, queryFn: adminApi.listEmployees });
}

function useEmployeesInvalidate() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: employeesKey });
}

export function useSyncFeishuContacts() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: adminApi.syncFeishuContacts,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: employeesKey });
      qc.invalidateQueries({ queryKey: departmentsKey });
      qc.invalidateQueries({ queryKey: contactSyncLogsKey });
    },
  });
}

export function useContactSyncLogs() {
  return useQuery({ queryKey: contactSyncLogsKey, queryFn: adminApi.listFeishuContactSyncLogs });
}

export function useUpdateEmployee() {
  const invalidate = useEmployeesInvalidate();
  return useMutation({
    mutationFn: ({ id, input }: { id: number; input: adminApi.EmployeeUpdateInput }) =>
      adminApi.updateEmployee(id, input),
    onSuccess: invalidate,
  });
}

export function useSetEmployeePermissions() {
  const invalidate = useEmployeesInvalidate();
  const currentUserId = useAuthStore((s) => s.user?.id);
  const setSession = useAuthStore((s) => s.setSession);
  return useMutation({
    mutationFn: ({ id, permissions }: { id: number; permissions: string[] }) =>
      adminApi.setEmployeePermissions(id, permissions),
    onSuccess: async (_data, { id }) => {
      invalidate();
      // Editing your own permissions must refresh the session so the nav (which
      // reads authStore.permissions) reflects the change without a page reload.
      if (id === currentUserId) {
        setSession(await getMe());
      }
    },
  });
}

export function useSetEmployeeStatus() {
  const invalidate = useEmployeesInvalidate();
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: 'active' | 'disabled' }) =>
      adminApi.setEmployeeStatus(id, status),
    onSuccess: invalidate,
  });
}

export function useDeleteEmployee() {
  const invalidate = useEmployeesInvalidate();
  return useMutation({
    mutationFn: (id: number) => adminApi.deleteEmployee(id),
    onSuccess: invalidate,
  });
}

// ---- Agent access ----

export function useAdminAgents() {
  return useQuery({ queryKey: adminAgentsKey, queryFn: adminApi.listAdminAgents });
}

export function useAgentAccess(agentId: number | null) {
  return useQuery({
    queryKey: agentAccessKey(agentId ?? 0),
    queryFn: () => adminApi.getAgentAccess(agentId!),
    enabled: agentId !== null,
  });
}

export function useAgentFeishuChatConfig(agentId: number) {
  return useQuery({
    queryKey: agentFeishuChatConfigKey(agentId),
    queryFn: () => adminApi.getAgentFeishuChatConfig(agentId),
  });
}

export function useUpdateAgentFeishuChatConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ agentId, input }: {
      agentId: number;
      input: adminApi.AgentFeishuChatConfigInput;
    }) => adminApi.updateAgentFeishuChatConfig(agentId, input),
    onSuccess: (data, { agentId }) => {
      queryClient.setQueryData(agentFeishuChatConfigKey(agentId), data);
      queryClient.invalidateQueries({ queryKey: agentAccessKey(agentId) });
      queryClient.invalidateQueries({ queryKey: adminAgentsKey });
      queryClient.invalidateQueries({ queryKey: ['chat-agents'] });
      queryClient.invalidateQueries({ queryKey: ['chat-agent-status'] });
    },
  });
}

export function useUpdateAgentPresentation() {
  const syncAgent = useSyncAgentPresentation();
  return useMutation({
    mutationFn: ({ agentId, input }: {
      agentId: number;
      input: adminApi.AgentPresentationInput;
    }) => adminApi.updateAgentPresentation(agentId, input),
    onSuccess: syncAgent,
  });
}

export function useUploadAgentAvatar() {
  const syncAgent = useSyncAgentPresentation();
  return useMutation({
    mutationFn: ({ agentId, file }: { agentId: number; file: File }) => (
      adminApi.uploadAgentAvatar(agentId, file)
    ),
    onSuccess: syncAgent,
  });
}

export function useRemoveAgentAvatar() {
  const syncAgent = useSyncAgentPresentation();
  return useMutation({
    mutationFn: adminApi.removeAgentAvatar,
    onSuccess: syncAgent,
  });
}

export function useReplaceAgentAccess() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ agentId, userIds, groupIds }: {
      agentId: number;
      userIds: number[];
      groupIds: number[];
    }) => (
      adminApi.replaceAgentAccess(agentId, { user_ids: userIds, group_ids: groupIds })
    ),
    onSuccess: (data) => {
      queryClient.setQueryData(agentAccessKey(data.agent.id), data);
      queryClient.invalidateQueries({ queryKey: adminAgentsKey });
    },
  });
}

// ---- Departments ----

export function useDepartments() {
  return useQuery({ queryKey: departmentsKey, queryFn: adminApi.listDepartments });
}

export function useCreateDepartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: adminApi.DepartmentInput) => adminApi.createDepartment(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: departmentsKey }),
  });
}

export function useUpdateDepartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, input }: { id: number; input: Partial<adminApi.DepartmentInput> }) =>
      adminApi.updateDepartment(id, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: departmentsKey }),
  });
}

export function useDeleteDepartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => adminApi.deleteDepartment(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: departmentsKey }),
  });
}

// ---- Notifications ----

export function useNotificationSettings() {
  return useQuery({ queryKey: notificationSettingsKey, queryFn: adminApi.listNotificationSettings });
}

export function useNotificationDeliverySummary() {
  return useQuery({
    queryKey: notificationDeliverySummaryKey,
    queryFn: adminApi.getNotificationDeliverySummary,
    refetchInterval: 30_000,
  });
}

export function useUpdateNotificationSetting() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ type, input }: {
      type: string;
      input: Partial<Pick<adminApi.NotificationChannelRuleOut, 'in_app_enabled' | 'feishu_enabled'>>;
    }) => adminApi.updateNotificationSetting(type, input),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: notificationSettingsKey });
      queryClient.invalidateQueries({ queryKey: notificationDeliverySummaryKey });
    },
  });
}

export function useTestFeishuNotification() {
  return useMutation({ mutationFn: adminApi.testFeishuNotification });
}

// 人员组 hooks 已迁至 features/groups/hooks.ts（feature:group 门控）。
