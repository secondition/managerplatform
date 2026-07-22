import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as adminApi from '@/api/admin';
import { getMe } from '@/api/auth';
import { useAuthStore } from '@/stores/authStore';

const employeesKey = ['admin-employees'] as const;
const departmentsKey = ['admin-departments'] as const;
const contactSyncLogsKey = ['admin-contact-sync-logs'] as const;

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

// 人员组 hooks 已迁至 features/groups/hooks.ts（feature:group 门控）。
