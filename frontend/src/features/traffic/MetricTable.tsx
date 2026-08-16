import { Fragment, useEffect, useRef, useState, type ReactNode } from 'react';
import { ChevronDown, ChevronRight, Eye, PencilLine, Plus, Users } from 'lucide-react';
import type { MetricDirection, TrafficMetricOut, WeekColumnOut } from '@/types/api';
import { fmtNum, toNum } from '@/lib/num';
import MetricCell from './MetricCell';
import MetricAssignmentPopover, { type AssignmentMode } from './MetricAssignmentPopover';
import FloatingPanel from './FloatingPanel';
import { useDeleteMetric, useUpdateMetric, useUpsertValue } from './hooks';

interface MetricTableProps {
  columns: WeekColumnOut[];
  metrics: TrafficMetricOut[];
  groupAssignments: boolean;
  showAssignmentControls: boolean;
  showAssignmentMeta: boolean;
  // Whether the window ends at the current week (rightmost col = 本周).
  isLatestWindow: boolean;
  onAddClick: () => void;
  addContent?: ReactNode;
  emptyContent?: ReactNode;
}

const DIRECTION_TEXT: Record<MetricDirection, string> = {
  increase: '越高越好',
  decrease: '越低越好',
};

type AssignmentState = {
  metric: TrafficMetricOut;
  mode: AssignmentMode;
  anchor: HTMLElement;
} | null;
type TargetField = 'weekly_target' | 'north_star_target';
type MetricGroup = { metric: TrafficMetricOut; assignments: TrafficMetricOut[] };

function groupByMetric(metrics: TrafficMetricOut[]): MetricGroup[] {
  const groups = new Map<number, MetricGroup>();
  metrics.forEach((metric) => {
    const group = groups.get(metric.id);
    if (group) {
      group.assignments.push(metric);
    } else {
      groups.set(metric.id, { metric, assignments: [metric] });
    }
  });
  return Array.from(groups.values());
}

// Weekly-target traffic-light table: 指标 | W(最近N周) | 近N周平均 | 周目标 | 北极星目标 | 操作.
// Week columns are the rolling window from GET /traffic/weeks.
export default function MetricTable({
  columns,
  metrics,
  groupAssignments,
  showAssignmentControls,
  showAssignmentMeta,
  isLatestWindow,
  onAddClick,
  addContent,
  emptyContent,
}: MetricTableProps) {
  const upsert = useUpsertValue();
  const deleteMetric = useDeleteMetric();
  const updateMetric = useUpdateMetric();
  const [assignment, setAssignment] = useState<AssignmentState>(null);
  const [expandedMetricIds, setExpandedMetricIds] = useState<Set<number>>(new Set());
  const columnCount = columns.length + 5;
  const metricGroups = groupByMetric(metrics);

  const openAssignment = (
    metric: TrafficMetricOut,
    mode: AssignmentMode,
    anchor: HTMLElement,
  ) => {
    setAssignment((current) =>
      current?.metric.id === metric.id && current.mode === mode
        ? null
        : { metric, mode, anchor },
    );
  };

  const handleDelete = (id: number, name: string) => {
    if (window.confirm(`确定要删除指标「${name}」、全部填写实例及其周值吗？此操作不可恢复。`)) {
      deleteMetric.mutate(id);
    }
  };

  const targetText = (m: TrafficMetricOut): string => {
    return fmtNum(m.weekly_target);
  };

  const weekLabel = (col: WeekColumnOut): string => {
    const start = col.week_start.split('-').slice(1).map(Number).join('.');
    const end = col.week_end.split('-').slice(1).map(Number).join('.');
    return `${start}-${end}`;
  };

  const toggleExpanded = (metricId: number) => {
    setExpandedMetricIds((current) => {
      const next = new Set(current);
      if (next.has(metricId)) next.delete(metricId);
      else next.add(metricId);
      return next;
    });
  };

  const renderAssignmentControls = (metric: TrafficMetricOut) => {
    const editorCount = metric.assignees.length;
    const viewerCount = metric.members.filter((member) => member.role === 'viewer').length;
    if (!showAssignmentControls || !metric.can_manage_members) {
      return (
        <span className="mt-1 inline-flex items-center gap-1 text-[10px] text-[#7890ad]">
          <Users size={10} />
          填写者 {editorCount} · 查看者 {viewerCount}
        </span>
      );
    }
    return (
      <div className="mt-1 flex flex-wrap gap-1.5">
        <button
          type="button"
          onClick={(event) => openAssignment(metric, 'editors', event.currentTarget)}
          className={`inline-flex h-6 items-center gap-1 rounded-md px-2 text-[10px] font-semibold transition-colors ${
            assignment?.metric.id === metric.id && assignment.mode === 'editors'
              ? 'bg-[var(--theme-accent)] text-white'
              : 'bg-[var(--theme-accent-soft)] text-[var(--theme-accent)] hover:brightness-[.98]'
          }`}
          aria-label={`管理填写者，当前${editorCount}人`}
        >
          <PencilLine size={10} />
          填写者 {editorCount}
        </button>
        <button
          type="button"
          onClick={(event) => openAssignment(metric, 'viewers', event.currentTarget)}
          className={`inline-flex h-6 items-center gap-1 rounded-md px-2 text-[10px] font-semibold transition-colors ${
            assignment?.metric.id === metric.id && assignment.mode === 'viewers'
              ? 'bg-[var(--theme-accent)] text-white'
              : 'bg-slate-100 text-[#506887] hover:bg-slate-200/70'
          }`}
          aria-label={`管理查看者，当前${viewerCount}人`}
        >
          <Eye size={10} />
          查看者 {viewerCount}
        </button>
      </div>
    );
  };

  const renderAssignmentRow = (metric: TrafficMetricOut, detail = false) => {
    const valueByWeek = new Map(metric.values.map((value) => [value.week_start, value]));
    const target = targetText(metric);
    return (
      <tr
        key={`${metric.id}:${metric.assignment_id ?? 'draft'}:${detail ? 'detail' : 'direct'}`}
        className={`border-b border-[#dbe3ef] transition-colors hover:bg-slate-50/40 ${detail ? 'bg-[#fbfdff]' : ''}`}
      >
        <td className={`sticky left-0 z-10 px-3 py-3 ${detail ? 'bg-[#fbfdff]' : 'bg-white'}`}>
          <div className={detail ? 'pl-7' : ''}>
            <div className="flex items-center gap-2">
              {detail ? (
                <span className="text-[12px] font-semibold text-[#385574]">
                  {metric.assignee?.name ?? '尚未指派'}
                </span>
              ) : (
                <MetricNameEditor
                  metric={metric}
                  submitting={updateMetric.isPending}
                  onSave={(name) => updateMetric.mutate({ id: metric.id, input: { name } })}
                />
              )}
              {metric.is_pending && (
                <span className="rounded-md bg-[#fff2d9] px-1.5 py-0.5 text-[10px] font-semibold text-[#b06b00]">本周未填</span>
              )}
            </div>
            <p className="mt-1 text-[10px] text-[#7890ad]">
              {detail ? `填写详情 · ${metric.unit || '-'} · ${DIRECTION_TEXT[metric.direction]}` : `${metric.unit || '-'} · 每周 · ${DIRECTION_TEXT[metric.direction]}`}
            </p>
            {!detail && showAssignmentMeta && (
              <>
                <p className="mt-1 text-[10px] font-medium text-[#506887]">
                  填写者：{metric.assignee?.name ?? '尚未指派'}
                </p>
                {renderAssignmentControls(metric)}
              </>
            )}
          </div>
        </td>

        {columns.map((column) => {
          const value = valueByWeek.get(column.week_start);
          const editable = Boolean(
            metric.can_edit_values
            && metric.assignment_id !== null
            && metric.assignee
            && column.week_start >= metric.assignee.effective_from,
          );
          return (
            <MetricCell
              key={column.week_start}
              value={value}
              editable={editable}
              targetLabel={`目标 ${target}`}
              onSave={(input) => {
                if (metric.assignment_id !== null) {
                  upsert.mutate({ assignmentId: metric.assignment_id, weekStart: column.week_start, input });
                }
              }}
            />
          );
        })}

        <td className="px-2 py-3 text-center font-mono text-[13px] text-slate-800">
          {metric.recent_avg === null ? <span className="text-zinc-300">—</span> : fmtNum(metric.recent_avg)}
        </td>

        {detail ? (
          <>
            <ReadOnlyTargetCell value={metric.weekly_target} />
            <ReadOnlyTargetCell value={metric.north_star_target} />
          </>
        ) : (
          <>
            <MetricTargetCell
              metric={metric}
              field="weekly_target"
              submitting={updateMetric.isPending}
              onSave={(value) => updateMetric.mutate({ id: metric.id, input: { weekly_target: value } })}
            />
            <MetricTargetCell
              metric={metric}
              field="north_star_target"
              submitting={updateMetric.isPending}
              onSave={(value) => updateMetric.mutate({ id: metric.id, input: { north_star_target: value } })}
            />
          </>
        )}

        <td className="px-2 py-3 text-center whitespace-nowrap">
          {!detail && metric.can_delete ? (
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
                      <span className="mt-0.5 text-[10px] font-semibold">本周</span>
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

          {groupAssignments
            ? metricGroups.map((group) => {
                const metric = group.metric;
                const details = group.assignments.filter((row) => row.assignment_id !== null);
                if (metric.my_role === 'assignee') return renderAssignmentRow(metric);

                const expanded = expandedMetricIds.has(metric.id);
                return (
                  <Fragment key={`group:${metric.id}`}>
                    <tr className="border-b border-[#dbe3ef] bg-white transition-colors hover:bg-slate-50/40">
                      <td className="sticky left-0 z-10 bg-white px-3 py-3">
                        <div className="flex items-start gap-2">
                          <button
                            type="button"
                            onClick={() => details.length > 0 && toggleExpanded(metric.id)}
                            disabled={details.length === 0}
                            className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md text-[#7890ad] transition-colors hover:bg-[var(--theme-accent-soft)] hover:text-[var(--theme-accent)] disabled:opacity-30"
                            aria-label={expanded ? '收起填写者详情' : '展开填写者详情'}
                          >
                            {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
                          </button>
                          <div>
                            <div className="flex items-center gap-2">
                              <MetricNameEditor
                                metric={metric}
                                submitting={updateMetric.isPending}
                                onSave={(name) => updateMetric.mutate({ id: metric.id, input: { name } })}
                              />
                              <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[10px] font-semibold text-[#506887]">
                                {details.length} 位填写者
                              </span>
                            </div>
                            <p className="mt-1 text-[10px] text-[#7890ad]">
                              {metric.unit || '-'} · 每周 · {DIRECTION_TEXT[metric.direction]}
                            </p>
                            {renderAssignmentControls(metric)}
                          </div>
                        </div>
                      </td>

                      {columns.map((column) => {
                        const eligible = details.filter(
                          (row) => row.assignee && column.week_start >= row.assignee.effective_from,
                        );
                        const filled = eligible.filter((row) =>
                          row.values.some(
                            (value) => value.week_start === column.week_start && value.value !== null,
                          ),
                        ).length;
                        const complete = eligible.length > 0 && filled === eligible.length;
                        return (
                          <td key={column.week_start} className="h-[86px] px-2 py-2 text-center align-middle">
                            {eligible.length === 0 ? (
                              <span className="text-zinc-300">—</span>
                            ) : (
                              <>
                                <span className={`inline-flex h-8 min-w-12 items-center justify-center rounded-full px-3 font-mono text-[12px] font-semibold ${
                                  complete ? 'bg-emerald-50 text-emerald-600' : 'bg-[#fff7e8] text-[#b06b00]'
                                }`}>
                                  {filled}/{eligible.length}
                                </span>
                                <div className="mt-1 text-[10px] text-[#7890ad]">已填写</div>
                              </>
                            )}
                          </td>
                        );
                      })}

                      <td className="px-2 py-3 text-center text-[11px] text-[#7890ad]">
                        {details.length > 0 ? '展开查看' : '—'}
                      </td>
                      <MetricTargetCell
                        metric={metric}
                        field="weekly_target"
                        submitting={updateMetric.isPending}
                        onSave={(value) => updateMetric.mutate({ id: metric.id, input: { weekly_target: value } })}
                      />
                      <MetricTargetCell
                        metric={metric}
                        field="north_star_target"
                        submitting={updateMetric.isPending}
                        onSave={(value) => updateMetric.mutate({ id: metric.id, input: { north_star_target: value } })}
                      />
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
                    {expanded && details.map((row) => renderAssignmentRow(row, true))}
                  </Fragment>
                );
              })
            : metrics.map((metric) => renderAssignmentRow(metric))}
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
            mode={assignment.mode}
            submitting={updateMetric.isPending}
            onCancel={() => setAssignment(null)}
            onSubmit={(ids) =>
              updateMetric.mutate(
                {
                  id: assignment.metric.id,
                  input: assignment.mode === 'editors'
                    ? { editor_ids: ids }
                    : { viewer_ids: ids },
                },
                { onSuccess: () => setAssignment(null) },
              )
            }
          />
        </FloatingPanel>
      )}
    </div>
  );
}

function ReadOnlyTargetCell({ value }: { value: string | number | null }) {
  return (
    <td className="h-[86px] px-2 py-3 text-center align-middle whitespace-nowrap">
      <span className={`font-mono text-[13px] ${value === null ? 'text-slate-400' : 'text-slate-700'}`}>
        {value === null ? '-' : fmtNum(value)}
      </span>
    </td>
  );
}

function MetricNameEditor({
  metric,
  submitting,
  onSave,
}: {
  metric: TrafficMetricOut;
  submitting: boolean;
  onSave: (name: string) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const committingRef = useRef(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(metric.name);

  useEffect(() => {
    if (!editing) setDraft(metric.name);
  }, [editing, metric.name]);

  useEffect(() => {
    if (editing) {
      inputRef.current?.focus();
      inputRef.current?.select();
    }
  }, [editing]);

  const startEdit = () => {
    if (!metric.can_edit_meta || submitting) return;
    setDraft(metric.name);
    committingRef.current = false;
    setEditing(true);
  };

  const cancel = () => {
    committingRef.current = true;
    setDraft(metric.name);
    setEditing(false);
  };

  const save = () => {
    if (committingRef.current || !editing) return;
    committingRef.current = true;
    const name = draft.trim();
    if (!name || name.length > 200) {
      setDraft(metric.name);
      setEditing(false);
      return;
    }
    if (name !== metric.name) onSave(name);
    setEditing(false);
  };

  if (editing) {
    return (
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
            event.preventDefault();
            cancel();
          }
        }}
        maxLength={200}
        aria-label="编辑指标名称"
        className="h-8 min-w-0 max-w-[210px] rounded-xl border-0 bg-[#eaf2ff] px-2 text-[13px] font-bold text-slate-950 outline-none focus:bg-[#e5efff]"
      />
    );
  }

  return (
    <span
      onDoubleClick={startEdit}
      title={metric.can_edit_meta ? '双击编辑指标名称' : undefined}
      className={`text-[13px] font-bold text-slate-950 ${
        metric.can_edit_meta ? 'cursor-text rounded px-1 -mx-1 hover:bg-[var(--theme-accent-soft)]' : ''
      }`}
    >
      {metric.name}
    </span>
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
