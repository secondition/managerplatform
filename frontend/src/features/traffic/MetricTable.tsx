import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Plus, Users } from 'lucide-react';
import type { MetricDirection, TrafficMetricOut, WeekColumnOut } from '@/types/api';
import { fmtNum, toNum } from '@/lib/num';
import MetricCell from './MetricCell';
import MetricAssignmentPopover from './MetricAssignmentPopover';
import FloatingPanel from './FloatingPanel';
import { useDeleteMetric, useUpdateMetric, useUpsertValue } from './hooks';

interface MetricTableProps {
  columns: WeekColumnOut[];
  metrics: TrafficMetricOut[];
  // Whether the window ends at the latest completed week (rightmost col = 上周).
  isLatestWindow: boolean;
  onAddClick: () => void;
  addContent?: ReactNode;
  emptyContent?: ReactNode;
}

const DIRECTION_TEXT: Record<MetricDirection, string> = {
  increase: '越高越好',
  decrease: '越低越好',
};

type AssignmentState = { metric: TrafficMetricOut; anchor: HTMLElement } | null;
type TargetField = 'weekly_target' | 'north_star_target';

// Weekly-target traffic-light table: 指标 | W(最近N周) | 近N周平均 | 周目标 | 北极星目标 | 操作.
// Week columns are the rolling window from GET /traffic/weeks.
export default function MetricTable({
  columns,
  metrics,
  isLatestWindow,
  onAddClick,
  addContent,
  emptyContent,
}: MetricTableProps) {
  const upsert = useUpsertValue();
  const deleteMetric = useDeleteMetric();
  const updateMetric = useUpdateMetric();
  const [assignment, setAssignment] = useState<AssignmentState>(null);
  const columnCount = columns.length + 5;

  const openAssignment = (metric: TrafficMetricOut, anchor: HTMLElement) => {
    setAssignment((current) => (current?.metric.id === metric.id ? null : { metric, anchor }));
  };

  const handleDelete = (id: number, name: string) => {
    if (window.confirm(`确定要删除指标「${name}」及其所有周值吗？此操作不可恢复。`)) {
      deleteMetric.mutate(id);
    }
  };

  const targetText = (m: TrafficMetricOut): string => {
    return fmtNum(m.weekly_target);
  };

  const shareText = (m: TrafficMetricOut): string => {
    const editorCount = m.members.filter((member) => member.role === 'editor').length;
    const viewerCount = m.members.filter((member) => member.role === 'viewer').length;
    return `填写 ${editorCount} · 查看 ${viewerCount} 指派`;
  };

  const weekLabel = (col: WeekColumnOut): string => {
    const start = col.week_start.split('-').slice(1).map(Number).join('.');
    const end = col.week_end.split('-').slice(1).map(Number).join('.');
    return `${start}-${end}`;
  };

  return (
    <div className="overflow-x-auto rounded-2xl border border-[#d7e0ec] bg-white">
      <table className="w-full min-w-[1120px] border-collapse text-xs">
        <thead>
          <tr className="border-b border-[#dbe3ef] bg-[#f8fbff] text-[11px] text-slate-500">
            <th className="sticky left-0 min-w-[260px] bg-[#f8fbff] px-3 py-3 text-left font-semibold">指标 / 共享</th>
            {columns.map((col, i) => {
              const isLast = isLatestWindow && i === columns.length - 1;
              return (
                <th key={col.week_start} className="min-w-[94px] px-1.5 py-2 font-semibold whitespace-nowrap align-middle">
                  {isLast ? (
                    <div className="mx-auto flex h-12 w-24 flex-col items-center justify-center rounded-xl bg-[var(--theme-accent-soft)] text-[var(--theme-accent)]">
                      <span className="text-[11px] font-semibold tabular-nums">{weekLabel(col)}</span>
                      <span className="mt-0.5 text-[10px] font-semibold">上周</span>
                    </div>
                  ) : (
                    <span className="text-[10px] font-medium tabular-nums text-[#506887]">{weekLabel(col)}</span>
                  )}
                </th>
              );
            })}
            <th className="min-w-[110px] px-2 py-3 font-semibold whitespace-nowrap">近{columns.length}周平均</th>
            <th className="min-w-[96px] px-2 py-3 font-semibold">周目标</th>
            <th className="min-w-[120px] px-2 py-3 font-semibold">北极星目标</th>
            <th className="min-w-[70px] px-2 py-3 font-semibold">操作</th>
          </tr>
        </thead>
        <tbody>
          {metrics.length === 0 && emptyContent && (
            <tr>
              <td colSpan={columnCount} className="px-4 py-7">
                {emptyContent}
              </td>
            </tr>
          )}

          {metrics.map((metric) => {
            const valueByWeek = new Map(metric.values.map((v) => [v.week_start, v]));
            const target = targetText(metric);
            return (
              <tr key={metric.id} className="border-b border-[#dbe3ef] transition-colors hover:bg-slate-50/40">
                {/* Name */}
                <td className="sticky left-0 z-10 bg-white px-3 py-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-bold text-slate-950">{metric.name}</span>
                    {metric.is_pending && (
                      <span className="rounded-md bg-[#fff2d9] px-1.5 py-0.5 text-[10px] font-semibold text-[#b06b00]">上周未填</span>
                    )}
                  </div>
                  <p className="mt-1 text-[10px] text-[#7890ad]">
                    {metric.unit || '-'} · 每周 · {DIRECTION_TEXT[metric.direction]}
                  </p>
                  <button
                    type="button"
                    onClick={(event) => metric.can_manage_members && openAssignment(metric, event.currentTarget)}
                    disabled={!metric.can_manage_members}
                    className={`mt-1 inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] transition-colors disabled:cursor-default ${
                      assignment?.metric.id === metric.id ? 'bg-[var(--theme-accent)] text-white' : 'bg-[var(--theme-accent-soft)] text-[var(--theme-accent)] hover:brightness-[.98]'
                    }`}
                  >
                    <Users size={10} />
                    {shareText(metric)}
                  </button>
                </td>

                {/* Week cells */}
                {columns.map((col) => (
                  <MetricCell
                    key={col.week_start}
                    value={valueByWeek.get(col.week_start)}
                    editable={metric.can_edit_values}
                    targetLabel={`目标 ${target}`}
                    onSave={(input) =>
                      upsert.mutate({ metricId: metric.id, weekStart: col.week_start, input })
                    }
                  />
                ))}

                {/* Recent average */}
                <td className="px-2 py-3 text-center font-mono text-[13px] text-slate-800">
                  {metric.recent_avg === null ? <span className="text-zinc-300">—</span> : fmtNum(metric.recent_avg)}
                </td>

                {/* Weekly target */}
                <MetricTargetCell
                  metric={metric}
                  field="weekly_target"
                  submitting={updateMetric.isPending}
                  onSave={(value) =>
                    updateMetric.mutate({ id: metric.id, input: { weekly_target: value } })
                  }
                />

                <MetricTargetCell
                  metric={metric}
                  field="north_star_target"
                  submitting={updateMetric.isPending}
                  onSave={(value) =>
                    updateMetric.mutate({ id: metric.id, input: { north_star_target: value } })
                  }
                />

                {/* Actions follow resource-level permissions. */}
                <td className="px-2 py-3 text-center whitespace-nowrap">
                  {metric.can_delete ? (
                    <button
                      onClick={() => handleDelete(metric.id, metric.name)}
                      className="rounded px-1.5 py-1 text-[13px] text-[#b8c4d3] transition-colors hover:bg-red-50 hover:text-red-500"
                      title="删除指标"
                    >
                      ×
                    </button>
                  ) : (
                    <span className="text-[10px] text-zinc-300">—</span>
                  )}
                </td>
              </tr>
            );
          })}
          <tr>
            <td colSpan={columnCount} className="p-0">
              {addContent ?? (
                <button
                  type="button"
                  onClick={onAddClick}
                  className="flex h-[52px] items-center gap-1 px-4 text-[13px] font-semibold text-[var(--theme-accent)] hover:text-[var(--theme-accent-hover)]"
                >
                  <Plus size={14} />
                  添加指标
                </button>
              )}
            </td>
          </tr>
        </tbody>
      </table>
      {assignment && (
        <FloatingPanel anchor={assignment.anchor} width={300} borderRadius={16} onClose={() => setAssignment(null)}>
          <MetricAssignmentPopover
            metric={assignment.metric}
            submitting={updateMetric.isPending}
            onCancel={() => setAssignment(null)}
            onSubmit={(input) =>
              updateMetric.mutate(
                { id: assignment.metric.id, input },
                { onSuccess: () => setAssignment(null) },
              )
            }
          />
        </FloatingPanel>
      )}
    </div>
  );
}

function MetricTargetCell({
  metric,
  field,
  submitting,
  onSave,
}: {
  metric: TrafficMetricOut;
  field: TargetField;
  submitting: boolean;
  onSave: (value: number | null) => void;
}) {
  const isWeekly = field === 'weekly_target';
  const inputRef = useRef<HTMLInputElement>(null);
  const committingRef = useRef(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const rawValue = isWeekly ? metric.weekly_target : metric.north_star_target;
  const display = rawValue === null ? '-' : fmtNum(rawValue);

  useEffect(() => {
    const num = toNum(rawValue);
    setDraft(num === null ? '' : String(num));
  }, [rawValue]);

  useEffect(() => {
    if (editing) inputRef.current?.focus();
  }, [editing]);

  const startEdit = () => {
    if (!metric.can_edit_meta || submitting) return;
    const num = toNum(rawValue);
    setDraft(num === null ? '' : String(num));
    committingRef.current = false;
    setEditing(true);
  };

  const save = () => {
    if (committingRef.current) return;
    committingRef.current = true;
    if (!editing) return;
    const trimmed = draft.trim();
    const value = trimmed === '' ? null : Number(trimmed);
    if ((isWeekly && value === null) || (value !== null && !Number.isFinite(value))) {
      const num = toNum(rawValue);
      setDraft(num === null ? '' : String(num));
      setEditing(false);
      return;
    }
    onSave(value);
    setEditing(false);
  };

  return (
    <td
      onDoubleClick={startEdit}
      title={metric.can_edit_meta ? `双击编辑${isWeekly ? '周目标' : '北极星目标'}` : undefined}
      className={`h-[86px] px-2 py-3 text-center align-middle whitespace-nowrap ${
        metric.can_edit_meta ? 'cursor-pointer hover:bg-[var(--theme-accent-soft)]' : ''
      }`}
    >
      <div className="flex h-8 items-center justify-center">
        {editing ? (
          <input
            ref={inputRef}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            onBlur={save}
            onKeyDown={(event) => {
              if (event.key === 'Enter') {
                event.preventDefault();
                save();
              }
              if (event.key === 'Escape') {
                committingRef.current = true;
                setEditing(false);
              }
            }}
            inputMode="decimal"
            className="h-8 w-16 rounded-xl border-0 bg-[#eaf2ff] px-2 text-center font-mono text-[13px] font-semibold text-slate-950 outline-none focus:bg-[#e5efff]"
          />
        ) : (
          <span className={`font-mono text-[13px] ${isWeekly ? 'font-semibold text-slate-950' : rawValue === null ? 'text-slate-400' : 'text-slate-700'}`}>
            {display}
          </span>
        )}
      </div>
    </td>
  );
}
