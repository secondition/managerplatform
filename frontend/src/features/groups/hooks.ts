import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import * as groupsApi from '@/api/groups';

const groupsKey = ['groups'] as const;
const importSourcesKey = ['group-import-sources'] as const;

export function useGroups() {
  return useQuery({ queryKey: groupsKey, queryFn: groupsApi.listGroups });
}

export function useGroupImportSources() {
  return useQuery({ queryKey: importSourcesKey, queryFn: groupsApi.listGroupImportSources });
}

function useGroupsInvalidate() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: groupsKey });
}

export function useCreateGroup() {
  const invalidate = useGroupsInvalidate();
  return useMutation({
    mutationFn: (input: groupsApi.GroupInput) => groupsApi.createGroup(input),
    onSuccess: invalidate,
  });
}

export function useUpdateGroup() {
  const invalidate = useGroupsInvalidate();
  return useMutation({
    mutationFn: ({ id, input }: { id: number; input: Partial<Omit<groupsApi.GroupInput, 'member_ids'>> }) =>
      groupsApi.updateGroup(id, input),
    onSuccess: invalidate,
  });
}

export function useSetGroupMembers() {
  const invalidate = useGroupsInvalidate();
  return useMutation({
    mutationFn: ({ id, memberIds }: { id: number; memberIds: number[] }) =>
      groupsApi.setGroupMembers(id, memberIds),
    onSuccess: invalidate,
  });
}

export function useCreateGroupFromDepartment() {
  const invalidate = useGroupsInvalidate();
  return useMutation({
    mutationFn: ({ departmentId, name }: { departmentId: number; name?: string | null }) =>
      groupsApi.createGroupFromDepartment(departmentId, name),
    onSuccess: invalidate,
  });
}

export function useDeleteGroup() {
  const invalidate = useGroupsInvalidate();
  return useMutation({
    mutationFn: (id: number) => groupsApi.deleteGroup(id),
    onSuccess: invalidate,
  });
}
