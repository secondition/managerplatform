import { useState, type ReactNode } from 'react';
import { Eye, PencilLine } from 'lucide-react';
import UserSelectPopover from '@/components/user/UserSelectPopover';
import { useAuthStore } from '@/stores/authStore';
import type { MetricDirection } from '@/types/api';
import type { CreateMetricInput } from '@/api/traffic';

interface MetricInlineFormProps {
  submitting: boolean;
  onCancel: () => void;
  onSubmit: (input: CreateMetricInput) => void;
}

const DIRECTIONS: { key: MetricDirection; label: string }[] = [
  { key: 'increase', label: '越高越好' },
  { key: 'decrease', label: '越低越好' },
];

export default function MetricInlineForm({ submitting, onCancel, onSubmit }: MetricInlineFormProps) {
  const currentUserId = useAuthStore((s) => s.user?.id ?? 0);
  const [direction, setDirection] = useState<MetricDirection>('increase');
  const [name, setName] = useState('');
  const [unit, setUnit] = useState('');
  const [weeklyTarget, setWeeklyTarget] = useState('');
  const [northStarTarget, setNorthStarTarget] = useState('');
  const [editorIds, setEditorIds] = useState<number[]>([]);
  const [viewerIds, setViewerIds] = useState<number[]>([]);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = () => {
    if (submitting) return;
    const target = Number(weeklyTarget);
    const northTarget = northStarTarget.trim() === '' ? null : Number(northStarTarget);
    if (!name.trim()) return setError('请填写指标名称。');
    if (weeklyTarget.trim() === '' || !Number.isFinite(target)) {
      return setError('请填写有效的周目标。');
    }
    if (northTarget !== null && !Number.isFinite(northTarget)) {
      return setError('请填写有效的北极星目标。');
    }
    setError(null);
    onSubmit({
      name: name.trim(),
      unit: unit.trim() || null,
      direction,
      weekly_target: target,
      north_star_target: northTarget,
      editor_ids: editorIds,
      viewer_ids: viewerIds,
    });
  };

  return (
    <div className="border-t border-[#dbe3ef] bg-white px-3 py-3 text-[12px]">
      {error && (
        <div className="mb-2 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-[11px] text-red-600">
          {error}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#7d8da3]">
        <span>方向</span>
        <div className="inline-flex gap-1">
          {DIRECTIONS.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setDirection(item.key)}
              className={`h-7 rounded-full border px-3 text-[11px] font-semibold transition-colors ${
                direction === item.key
                  ? 'border-[var(--theme-accent)] bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]'
                  : 'border-[#d7e0ec] bg-white text-slate-600 hover:border-[var(--theme-accent)]'
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
        <span>每周跟进一个指标，达到周目标就绿灯</span>
      </div>

      <div className="mt-3 grid gap-3 md:grid-cols-[220px_88px_120px_170px]">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="指标名称（如 每周新增客户）"
          className={INPUT}
        />
        <input
          value={unit}
          onChange={(e) => setUnit(e.target.value)}
          placeholder="单位"
          className={INPUT}
        />
        <input
          value={weeklyTarget}
          onChange={(e) => setWeeklyTarget(e.target.value)}
          inputMode="decimal"
          placeholder="周目标"
          className={INPUT}
        />
        <input
          value={northStarTarget}
          onChange={(e) => setNorthStarTarget(e.target.value)}
          inputMode="decimal"
          placeholder="北极星目标（长期，可选）"
          className={INPUT}
        />
      </div>

      <div className="mt-3 grid max-w-[560px] gap-3 md:grid-cols-2">
        <MemberBox
          icon={<PencilLine size={13} />}
          title="填写人"
          selectedCount={editorIds.length}
          selectedIds={editorIds}
          excludeIds={viewerIds}
          onChange={setEditorIds}
        />
        <MemberBox
          icon={<Eye size={13} />}
          title="查看人"
          selectedCount={viewerIds.length}
          selectedIds={viewerIds}
          excludeIds={[currentUserId, ...editorIds]}
          onChange={setViewerIds}
        />
      </div>

      <div className="mt-3 flex items-center gap-2">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={submitting}
          className="h-7 rounded-md bg-[var(--theme-accent)] px-3 text-[12px] font-semibold text-white shadow-sm transition-colors hover:bg-[var(--theme-accent-hover)] disabled:opacity-50"
        >
          {submitting ? '添加中…' : '添加'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="h-7 rounded-md border border-[#d7e0ec] bg-white px-3 text-[12px] text-slate-600 hover:bg-slate-50"
        >
          取消
        </button>
        <span className="text-[11px] text-[#8a9ab1]">创建人如需填写，也要加入填写人</span>
      </div>
    </div>
  );
}

function MemberBox({
  icon,
  title,
  selectedCount,
  selectedIds,
  excludeIds,
  onChange,
}: {
  icon: ReactNode;
  title: string;
  selectedCount: number;
  selectedIds: number[];
  excludeIds: number[];
  onChange: (ids: number[]) => void;
}) {
  return (
    <div className="rounded-xl border border-[#dfe7f1] bg-white px-3 py-2">
      <div className="mb-1 flex items-center justify-between text-[11px]">
        <span className="inline-flex items-center gap-1.5 font-semibold text-[#1d3350]">
          {icon}
          {title}
        </span>
        <span className="text-[#8a9ab1]">已选 {selectedCount}</span>
      </div>
      <UserSelectPopover
        label="选择人员 / 人员组"
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

const INPUT =
  'h-9 rounded-xl border border-[#172033] bg-white px-3 text-[13px] text-slate-800 outline-none placeholder:text-[#7d8da3] focus:border-[var(--theme-accent)] focus:ring-2 focus:ring-[var(--theme-accent-ring)]';
