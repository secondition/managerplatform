import { useEffect, useState, type ReactNode } from 'react';
import { Eye, PencilLine } from 'lucide-react';
import UserSelectPopover from '@/components/user/UserSelectPopover';
import { useAuthStore } from '@/stores/authStore';
import type { TrafficMetricOut } from '@/types/api';

interface MetricAssignmentPopoverProps {
  metric: TrafficMetricOut;
  submitting: boolean;
  onCancel: () => void;
  onSubmit: (input: { editor_ids: number[]; viewer_ids: number[] }) => void;
}

export default function MetricAssignmentPopover({
  metric,
  submitting,
  onCancel,
  onSubmit,
}: MetricAssignmentPopoverProps) {
  const currentUserId = useAuthStore((s) => s.user?.id ?? 0);
  const [editorIds, setEditorIds] = useState<number[]>([]);
  const [viewerIds, setViewerIds] = useState<number[]>([]);

  useEffect(() => {
    setEditorIds(metric.members.filter((member) => member.role === 'editor').map((member) => member.user_id));
    setViewerIds(metric.members.filter((member) => member.role === 'viewer').map((member) => member.user_id));
  }, [metric]);

  return (
    <div className="w-[300px] rounded-2xl border border-[#d7e0ec] bg-white p-3 text-[12px]">
      <h3 className="mb-3 text-[13px] font-bold text-slate-950">指派「{metric.name}」</h3>
      <MemberPicker
        icon={<PencilLine size={13} />}
        title="填写人（可录数值）"
        selectedIds={editorIds}
        selectedCount={editorIds.length}
        excludeIds={viewerIds}
        onChange={setEditorIds}
      />
      <MemberPicker
        icon={<Eye size={13} />}
        title="查看人（只读）"
        selectedIds={viewerIds}
        selectedCount={viewerIds.length}
        excludeIds={[currentUserId, ...editorIds]}
        onChange={setViewerIds}
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
          onClick={() => onSubmit({ editor_ids: editorIds, viewer_ids: viewerIds })}
          className="h-8 rounded-md bg-[var(--theme-accent)] px-3 text-[12px] font-semibold text-white shadow-sm hover:bg-[var(--theme-accent-hover)] disabled:opacity-50"
        >
          保存
        </button>
      </div>
    </div>
  );
}

function MemberPicker({
  icon,
  title,
  selectedIds,
  selectedCount,
  excludeIds,
  onChange,
}: {
  icon: ReactNode;
  title: string;
  selectedIds: number[];
  selectedCount: number;
  excludeIds: number[];
  onChange: (ids: number[]) => void;
}) {
  return (
    <div className="mb-2">
      <div className="mb-1 flex items-center justify-between text-[11px]">
        <span className="inline-flex items-center gap-1.5 font-semibold text-[#1d3350]">
          {icon}
          {title}
        </span>
        <span className="text-[#8a9ab1]">已选 {selectedCount}</span>
      </div>
      <UserSelectPopover
        label="搜索同事姓名/部门..."
        multiple
        includeGroups
        selectedIds={selectedIds}
        excludeIds={excludeIds}
        onChange={onChange}
        triggerClassName="h-8 w-full justify-start rounded-lg border border-[#d7e0ec] bg-white px-2 text-left text-[11px] text-[#93a1b5] hover:bg-white"
      />
    </div>
  );
}
