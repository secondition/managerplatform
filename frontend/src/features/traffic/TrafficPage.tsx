import { useState } from 'react';
import { AlertCircle, HelpCircle } from 'lucide-react';
import { dayjs, toApiDate, type Dayjs } from '@/lib/date';
import type { TrafficMetricOut, WeekColumnOut } from '@/types/api';
import Spinner from '@/components/ui/Spinner';
import WeekPager, { anchorToApi } from './WeekPager';
import MetricTable from './MetricTable';
import MetricInlineForm from './MetricInlineForm';
import { useWeekColumns, useMetrics, useCreateMetric } from './hooks';

type MetricTab = 'all' | 'created' | 'pending' | 'viewable';

const TABS: { key: MetricTab; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'created', label: '我创建的' },
  { key: 'pending', label: '待我填写' },
  { key: 'viewable', label: '我可查看' },
];

const WEEK_COUNT = 5;

function previewWeekColumns(anchor: Dayjs | null, count: number): WeekColumnOut[] {
  const latest = dayjs().startOf('isoWeek');
  const end = anchor ?? latest;
  return Array.from({ length: count }, (_, i) => {
    const weekStart = end.subtract((count - 1 - i) * 7, 'day');
    const weekEnd = weekStart.add(6, 'day');
    return {
      week_index: weekStart.isoWeek(),
      label: `${weekStart.format('M.D')}-${weekEnd.format('M.D')}`,
      week_start: toApiDate(weekStart),
      week_end: toApiDate(weekEnd),
      is_empty: false,
    };
  });
}

function previewMetrics(columns: WeekColumnOut[]): TrafficMetricOut[] {
  if (columns.length === 0) return [];
  const assignees = [
    {
      assignment_id: 9101,
      user_id: 1,
      name: '韩梅梅',
      avatar_url: null,
      effective_from: columns[0].week_start,
    },
    {
      assignment_id: 9102,
      user_id: 2,
      name: '李雷',
      avatar_url: null,
      effective_from: columns[0].week_start,
    },
  ];
  return assignees.map((assignee, assigneeIndex) => {
    const values = columns
      .filter(
        (_, columnIndex) =>
          columnIndex < columns.length - (assigneeIndex === 0 ? 1 : 0),
      )
      .map((column, columnIndex) => {
        const value = 8 + assigneeIndex * 3 + columnIndex;
        return {
          id: 9200 + assigneeIndex * 10 + columnIndex,
          metric_id: 9001,
          assignment_id: assignee.assignment_id,
          week_start: column.week_start,
          week_end: column.week_end,
          value,
          status: value >= 10 ? 'on_target' as const : 'missed' as const,
          note: columnIndex === columns.length - 2 ? '客户渠道逐步恢复' : null,
        };
      });
    return {
      id: 9001,
      assignment_id: assignee.assignment_id,
      owner_id: 1,
      assignee,
      name: '每周新增客户',
      unit: '个',
      direction: 'increase',
      weekly_target: 10,
      north_star_target: 20,
      sort_order: 1,
      values,
      recent_avg: values.reduce((sum, item) => sum + item.value, 0) / values.length,
      status: values.some((item) => item.status === 'missed') ? 'missed' : 'on_target',
      members: [{ user_id: 3, name: '王芳', avatar_url: null, role: 'viewer' }],
      assignees,
      my_role: 'owner',
      can_edit_values: assignee.user_id === 1,
      can_edit_meta: true,
      can_manage_members: true,
      can_delete: true,
      is_pending: assignee.user_id === 1 && values.length < columns.length,
    };
  });
}

function filterByTab(metrics: TrafficMetricOut[], tab: MetricTab): TrafficMetricOut[] {
  switch (tab) {
    case 'created':
      return metrics.filter((m) => m.my_role === 'owner');
    case 'pending':
      return metrics.filter((m) => m.is_pending);
    case 'viewable':
      // Metrics shared with me where I'm not the owner.
      return metrics.filter((m) => m.my_role !== 'owner');
    default:
      return metrics;
  }
}

function metricCount(metrics: TrafficMetricOut[], tab: MetricTab): number {
  return new Set(filterByTab(metrics, tab).map((metric) => metric.id)).size;
}

export default function TrafficPage() {
  const preview = import.meta.env.DEV && new URLSearchParams(window.location.search).get('preview') === '1';
  // null anchor = current week; paging sets an explicit Monday.
  const [anchor, setAnchor] = useState<Dayjs | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [tab, setTab] = useState<MetricTab>(() => {
    const requested = new URLSearchParams(window.location.search).get('tab');
    return TABS.some((item) => item.key === requested) ? requested as MetricTab : 'all';
  });

  const windowKey = { end: anchorToApi(anchor), count: WEEK_COUNT };
  const columns = useWeekColumns(windowKey);
  const metrics = useMetrics(windowKey);
  const createMetric = useCreateMetric();

  const isLoading = columns.isLoading || metrics.isLoading;
  const isError = columns.isError || metrics.isError;
  const weekColumns = columns.data?.length ? columns.data : preview ? previewWeekColumns(anchor, WEEK_COUNT) : [];
  const availableMetrics = metrics.data?.length
    ? metrics.data
    : preview
      ? previewMetrics(weekColumns)
      : [];
  const visibleMetrics = filterByTab(availableMetrics, tab);

  return (
    <div className="workspace-page space-y-3">
      {/* Header */}
      <div className="flex flex-col items-start justify-between gap-4 md:flex-row md:items-center">
        <div className="flex items-center gap-2"><h2 className="text-[22px] font-bold text-slate-950">周关键指标 · 最近5周</h2><HelpCircle size={14} className="text-slate-300" /></div>
        <div className="flex items-center gap-3">
          <WeekPager anchor={anchor} count={WEEK_COUNT} onChange={setAnchor} />
        </div>
      </div>

      {/* Nav tabs */}
      <div className="flex flex-wrap items-center gap-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`h-7 rounded-full border px-3 text-[12px] font-medium shadow-sm transition-colors ${
              tab === t.key ? 'border-[var(--theme-accent)] bg-[var(--theme-accent)] text-white hover:text-white' : 'border-[#d7e0ec] bg-white text-slate-600 hover:border-[var(--theme-accent)]'
            }`}
          >
          {t.label} <span className={`ml-1 rounded-full px-1.5 py-0.5 text-[10px] ${tab === t.key ? 'bg-white/20' : 'bg-slate-100 text-[#7d8da3]'}`}>{metricCount(availableMetrics, t.key)}</span>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#70829a]"><span><i className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-emerald-600" />已录入</span><span><i className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-slate-300" />未推进</span><span><i className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-red-500" />异常</span><span>· 双击单元格录入数值，双击指标名称、目标/起点可改（仅你创建的）</span></div>

      {/* Body */}
      {isLoading && !preview ? (
        <Spinner label="正在加载指标…" />
      ) : isError && !preview ? (
        <div className="flex items-center gap-2 rounded-2xl bg-red-50 border border-red-100 px-4 py-3 text-xs text-red-600">
          <AlertCircle size={14} />
          加载指标失败，请稍后重试。
        </div>
      ) : (
        <MetricTable
          columns={weekColumns}
          metrics={visibleMetrics}
          groupAssignments={tab !== 'pending'}
          showAssignmentControls={tab === 'created'}
          showAssignmentMeta={tab !== 'pending'}
          isLatestWindow={anchor === null}
          onAddClick={() => setShowAdd(true)}
          addContent={
            showAdd ? (
              <MetricInlineForm
                submitting={createMetric.isPending}
                onCancel={() => setShowAdd(false)}
                onSubmit={(input) =>
                  createMetric.mutate(input, { onSuccess: () => setShowAdd(false) })
                }
              />
            ) : undefined
          }
          emptyContent={
            <div className="min-h-[120px] text-center text-[13px] text-[#7d8da3]">
              <p>{availableMetrics.length === 0 ? '本月还没有你参与的指标，点下方「添加指标」开始' : '当前筛选下没有指标。'}</p>
              {availableMetrics.length === 0 && (
                <div className="mx-auto mt-5 max-w-[520px] rounded-2xl border border-[#d7e0ec] bg-white p-5 text-left text-[12px] leading-6 text-[#70829a]">
                  <strong className="text-[14px] text-[#255b91]">用红绿灯可以做到什么</strong>
                  <p>把你负责的关键指标挂出来，每周打一次分：绿=达标、红=没达标。自己对进度心里有数，别人也能直接看到，不用反复报数据。</p>
                </div>
              )}
            </div>
          }
        />
      )}
    </div>
  );
}
