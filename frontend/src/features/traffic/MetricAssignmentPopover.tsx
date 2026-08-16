import { useEffect, useState } from 'react';
import { Eye, PencilLine, UserPlus, X } from 'lucide-react';
import UserSelectPopover from '@/components/user/UserSelectPopover';
import { useAuthStore } from '@/stores/authStore';
import type { TrafficMetricOut, UserBrief } from '@/types/api';

export type AssignmentMode = 'editors' | 'viewers';

interface MetricAssignmentPopoverProps {
  metric: TrafficMetricOut;
  mode: AssignmentMode;
  submitting: boolean;
  onCancel: () => void;
  onSubmit: (ids: number[]) => void;
}

export default function MetricAssignmentPopover({
  metric,
  mode,
  submitting,
  onCancel,
  onSubmit,
}: MetricAssignmentPopoverProps) {
  const currentUserId = useAuthStore((state) => state.user?.id ?? 0);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [selectedUsers, setSelectedUsers] = useState<UserBrief[]>([]);
  const isEditorMode = mode === 'editors';

  useEffect(() => {
    const people = isEditorMode
      ? metric.assignees.map((assignee) => ({
          id: assignee.user_id,
          name: assignee.name,
          avatar_url: assignee.avatar_url,
          department_id: null,
        }))
      : metric.members
          .filter((member) => member.role === 'viewer')
          .map((member) => ({
            id: member.user_id,
            name: member.name,
            avatar_url: member.avatar_url,
            department_id: null,
          }));
    setSelectedIds(people.map((person) => person.id));
    setSelectedUsers(people);
  }, [isEditorMode, metric]);

  const handleChange = (ids: number[], resolvedUsers: UserBrief[] = []) => {
    setSelectedIds(ids);
    setSelectedUsers((current) => {
      const peopleById = new Map<number, UserBrief>();
      current.forEach((person) => peopleById.set(person.id, person));
      resolvedUsers.forEach((person) => peopleById.set(person.id, person));
      return ids.map(
        (id) =>
          peopleById.get(id) ?? {
            id,
            name: `用户 ${id}`,
            avatar_url: null,
            department_id: null,
          },
      );
    });
  };

  const removePerson = (userId: number) => {
    handleChange(
      selectedIds.filter((id) => id !== userId),
      selectedUsers.filter((person) => person.id !== userId),
    );
  };

  const excludeIds = isEditorMode
    ? metric.members.filter((member) => member.role === 'viewer').map((member) => member.user_id)
    : [currentUserId, ...metric.assignees.map((assignee) => assignee.user_id)];

  return (
    <div className="w-[300px] rounded-2xl border border-[#d7e0ec] bg-white p-3 text-[12px]">
      <div className="mb-3 flex items-start gap-2">
        <span className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]">
          {isEditorMode ? <PencilLine size={14} /> : <Eye size={14} />}
        </span>
        <div>
          <h3 className="text-[13px] font-bold text-slate-950">
            {isEditorMode ? '管理填写者' : '管理查看者'}
          </h3>
          <p className="mt-0.5 text-[10px] leading-4 text-[#7890ad]">
            {isEditorMode ? '填写者拥有自己的指标实例和周值。' : '查看者可以看到所有填写者的数据，但不能录入。'}
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-[#dfe7f1] bg-[#fbfdff] p-2">
        <div className="mb-2 flex items-center justify-between text-[10px]">
          <span className="font-semibold text-[#506887]">已选人员</span>
          <span className="text-[#8a9ab1]">{selectedIds.length} 人</span>
        </div>
        <div className="flex min-h-8 flex-wrap gap-1.5">
          {selectedUsers.length === 0 ? (
            <span className="py-1 text-[11px] text-[#a1adbd]">暂未选择人员</span>
          ) : (
            selectedUsers.map((person) => (
              <span
                key={person.id}
                className="inline-flex h-7 items-center gap-1 rounded-full border border-[#d7e3f2] bg-white pl-2.5 pr-1.5 text-[11px] font-medium text-[#385574]"
              >
                {person.name}
                <button
                  type="button"
                  onClick={() => removePerson(person.id)}
                  className="flex h-4 w-4 items-center justify-center rounded-full text-[#9aa9bb] transition-colors hover:bg-red-50 hover:text-red-500"
                  aria-label={`移除${person.name}`}
                >
                  <X size={11} />
                </button>
              </span>
            ))
          )}
        </div>
      </div>

      <UserSelectPopover
        label="添加人员 / 人员组"
        icon={<UserPlus size={12} />}
        multiple
        includeGroups
        selectedIds={selectedIds}
        selectedUsers={selectedUsers}
        excludeIds={excludeIds}
        onChange={handleChange}
        triggerClassName="mt-2 h-8 w-full justify-center rounded-lg border border-dashed border-[#cbd8e8] bg-white px-2 text-[11px] font-semibold text-[var(--theme-accent)] hover:border-[var(--theme-accent)] hover:bg-[var(--theme-accent-soft)]"
      />

      <div className="mt-3 flex justify-end gap-2">
        <button
          type="button"
          onClick={onCancel}
          className="h-8 rounded-md border border-[#d7e0ec] bg-white px-3 text-[12px] text-slate-600 hover:bg-slate-50"
        >
          取消
        </button>
        <button
          type="button"
          disabled={submitting}
          onClick={() => onSubmit(selectedIds)}
          className="h-8 rounded-md bg-[var(--theme-accent)] px-3 text-[12px] font-semibold text-white shadow-sm hover:bg-[var(--theme-accent-hover)] disabled:opacity-50"
        >
          保存
        </button>
      </div>
    </div>
  );
}
