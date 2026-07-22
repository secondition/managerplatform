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
  const latest = dayjs().startOf('isoWeek').subtract(7, 'day');
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

export default function TrafficPage() {
  const preview = import.meta.env.DEV && new URLSearchParams(window.location.search).get('preview') === '1';
  // null anchor = latest completed week; paging sets an explicit Monday.
  const [anchor, setAnchor] = useState<Dayjs | null>(null);
  const [showAdd, setShowAdd] = useState(false);
  const [tab, setTab] = useState<MetricTab>('all');

  const windowKey = { end: anchorToApi(anchor), count: WEEK_COUNT };
  const columns = useWeekColumns(windowKey);
  const metrics = useMetrics(windowKey);
  const createMetric = useCreateMetric();

  const isLoading = columns.isLoading || metrics.isLoading;
  const isError = columns.isError || metrics.isError;
  const visibleMetrics = filterByTab(metrics.data ?? [], tab);
  const weekColumns = columns.data?.length ? columns.data : preview ? previewWeekColumns(anchor, WEEK_COUNT) : [];

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
            {t.label} <span className={`ml-1 rounded-full px-1.5 py-0.5 text-[10px] ${tab === t.key ? 'bg-white/20' : 'bg-slate-100 text-[#7d8da3]'}`}>{filterByTab(metrics.data ?? [], t.key).length}</span>
          </button>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-3 text-[11px] text-[#70829a]"><span><i className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-emerald-600" />已录入</span><span><i className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-slate-300" />未推进</span><span><i className="mr-1.5 inline-block h-2.5 w-2.5 rounded-full bg-red-500" />异常</span><span>· 双击单元格录入数值，双击目标/起点可改（仅你创建的）</span></div>

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
              <p>{(metrics.data?.length ?? 0) === 0 ? '本月还没有你参与的指标，点下方「添加指标」开始' : '当前筛选下没有指标。'}</p>
              {(metrics.data?.length ?? 0) === 0 && (
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
