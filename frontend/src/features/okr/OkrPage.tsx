import { useRef, useState, type FormEvent } from 'react';
import { AlertCircle, ChevronDown, HelpCircle, Plus } from 'lucide-react';
import { dayjs, toApiMonth, type Dayjs } from '@/lib/date';
import { toNum } from '@/lib/num';
import Spinner from '@/components/ui/Spinner';
import AnchoredPopover from '@/components/ui/AnchoredPopover';
import ObjectiveCard from './ObjectiveCard';
import MonthlyReport from './MonthlyReport';
import OkrReviewCard from './OkrReviewCard';
import { useOkrMonth, useCreateObjective, useReorderObjectives } from './hooks';
import { useAiFeatureFlags } from '@/features/daily/aiHooks';

type OkrView = 'okr' | 'report';

export default function OkrPage() {
  const preview = import.meta.env.DEV && new URLSearchParams(window.location.search).get('preview') === '1';
  const [month, setMonth] = useState<Dayjs>(dayjs().startOf('month'));
  const [view, setView] = useState<OkrView>('okr');
  const [addingObjective, setAddingObjective] = useState(false);
  const [draggingObjectiveId, setDraggingObjectiveId] = useState<number | null>(null);
  const [previewObjectiveIds, setPreviewObjectiveIds] = useState<number[] | null>(null);

  const monthStr = toApiMonth(month);
  const okr = useOkrMonth(monthStr);
  const createObjective = useCreateObjective(monthStr);
  const reorderObjectives = useReorderObjectives(monthStr);
  const flags = useAiFeatureFlags();
  const objectives = okr.data?.objectives ?? [];
  const visibleObjectives = previewObjectiveIds
    ? previewObjectiveIds.map((id) => objectives.find((objective) => objective.id === id)).filter((objective): objective is typeof objectives[number] => Boolean(objective))
    : objectives;
  const reviewScore = okr.data?.review.status === 'ready'
    ? toNum(okr.data.review.quality_score)
    : null;

  const avgProgress = objectives.length > 0
    ? Math.round(objectives.reduce((sum, objective) => sum + (toNum(objective.progress) ?? 0), 0) / objectives.length)
    : 0;

  return (
    <div className="workspace-page space-y-2 text-[12px]">
      <div className="rounded-none bg-transparent">
        <div className="flex min-h-[38px] flex-wrap items-center justify-between gap-3">
          <YearPicker month={month} onChange={setMonth} />
          <ViewSwitch view={view} onChange={setView} />
        </div>
        <MonthTabs month={month} onChange={setMonth} />
      </div>

      {okr.isLoading && !preview ? (
        <Spinner label="正在加载 OKR…" />
      ) : okr.isError && !preview ? (
        <div className="flex items-center gap-2 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-xs text-red-600">
          <AlertCircle size={14} />
          加载 OKR 失败，请稍后重试。
        </div>
      ) : view === 'report' ? (
        okr.data && (
          <MonthlyReport
            month={monthStr}
            sections={okr.data.monthly_report}
            monthLabel={month.format('YYYY年M月')}
            aiEnabled={Boolean(flags.data?.okr_review_enabled)}
          />
        )
      ) : (
        <>
          <section className="workspace-card flex min-h-[66px] flex-wrap items-center justify-between gap-3 px-4 py-3">
            <div>
              <h1 className="text-[16px] font-semibold leading-5 text-slate-950">本月 OKR</h1>
              <p className="mt-1 text-[11px] leading-4 text-slate-400">{month.format('M月')}的目标与关键结果</p>
            </div>
            <div className="flex items-center gap-2 text-[12px] leading-none text-slate-400">
              <span className="rounded-full bg-slate-50 px-3.5 py-2">均分 <b className="ml-1 text-[12px] font-semibold text-red-500">{avgProgress}%</b></span>
              <span className="rounded-full bg-slate-50 px-3.5 py-2">点评 <b className="ml-1 text-[12px] font-semibold text-[var(--theme-accent)]">{reviewScore ?? '--'}</b></span>
            </div>
          </section>

          <div className="space-y-2">
            {visibleObjectives.map((objective, index) => (
              <ObjectiveCard key={objective.id} index={index + 1} month={monthStr} objective={objective} onMove={(targetId, before) => {
                const next = [...(previewObjectiveIds ?? objectives.map((item) => item.id))];
                const sourceIndex = next.indexOf(targetId);
                const [moved] = next.splice(sourceIndex, 1);
                const targetIndex = next.indexOf(objective.id);
                const insertIndex = targetIndex < 0 ? next.length : targetIndex + (before ? 0 : 1);
                next.splice(insertIndex, 0, moved);
                setPreviewObjectiveIds(next);
              }}
              isDragging={draggingObjectiveId === objective.id}
              draggingId={draggingObjectiveId}
              onDragStart={() => {
                setDraggingObjectiveId(objective.id);
                setPreviewObjectiveIds(objectives.map((item) => item.id));
              }}
              onDragEnd={() => {
                setDraggingObjectiveId(null);
                setPreviewObjectiveIds(null);
              }}
              onDropOrder={(ids) => {
                reorderObjectives.mutate(ids, {
                  onSettled: () => {
                    setDraggingObjectiveId(null);
                    setPreviewObjectiveIds(null);
                  },
                });
              }} />
            ))}
            {addingObjective ? (
              <NewObjectiveForm
                index={objectives.length + 1}
                submitting={createObjective.isPending}
                onCancel={() => setAddingObjective(false)}
                onSubmit={(title) => createObjective.mutate(
                  { month: monthStr, title },
                  { onSuccess: () => setAddingObjective(false) },
                )}
              />
            ) : (
              <button
                onClick={() => setAddingObjective(true)}
                className="flex h-11 w-full items-center gap-1.5 rounded-xl border border-dashed border-[#cfdbea] px-4 text-[12px] font-medium text-[var(--theme-accent)] hover:border-[var(--theme-accent)] hover:bg-[var(--theme-accent-soft)]"
              >
                <Plus size={12} />
                添加新目标
              </button>
            )}
          </div>

          {(flags.data?.okr_review_enabled || okr.data?.review.status === 'ready') && <OkrReviewCard month={monthStr} />}
        </>
      )}
    </div>
  );
}

function ViewSwitch({ view, onChange }: { view: OkrView; onChange: (value: OkrView) => void }) {
  const itemClass = (active: boolean) =>
    active
      ? 'inline-flex h-7 min-w-[52px] items-center justify-center rounded-full bg-[var(--theme-accent)] px-3.5 text-[12px] font-semibold leading-none text-white shadow-[0_4px_12px_var(--theme-accent-ring)]'
      : 'inline-flex h-7 min-w-[52px] items-center justify-center rounded-full border border-[#e1e8f2] bg-white px-3.5 text-[12px] font-medium leading-none text-slate-600 transition-colors hover:border-[#cbd7e8] hover:text-slate-700';

  return (
    <div className="flex shrink-0 items-center gap-1.5">
      <button type="button" onClick={() => onChange('okr')} className={itemClass(view === 'okr')}>
        OKR
      </button>
      <button type="button" onClick={() => onChange('report')} className={itemClass(view === 'report')}>
        月报
      </button>
    </div>
  );
}

function YearPicker({ month, onChange }: { month: Dayjs; onChange: (value: Dayjs) => void }) {
  const [open, setOpen] = useState(false);
  const anchorRef = useRef<HTMLDivElement | null>(null);
  const currentYear = dayjs().year();
  const years = Array.from({ length: 6 }, (_, index) => currentYear - 4 + index);

  return (
    <div className="flex items-center gap-2.5">
      <HelpCircle size={15} strokeWidth={1.8} className="text-slate-300" />
      <div ref={anchorRef} className="relative flex items-center gap-2">
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="inline-flex h-7 items-center justify-center rounded-full bg-[var(--theme-accent-soft)] px-3 text-[12px] font-semibold leading-none tracking-wide text-[var(--theme-accent)]"
        >
          {month.year()}年
        </button>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="flex h-7 w-7 items-center justify-center rounded-full border border-[#e2e8f0] bg-white text-slate-400 transition-colors hover:border-slate-300 hover:text-slate-600"
          aria-label="选择年份"
        >
          <ChevronDown size={14} />
        </button>
        <AnchoredPopover
          anchor={open ? anchorRef.current : null}
          width={112}
          offset={6}
          zIndex={1100}
          closeOnScroll
          onClose={() => setOpen(false)}
        >
          <div className="overflow-hidden rounded-xl border border-[#e6eaf1] bg-white py-1">
            {years.map((year) => (
              <button
                key={year}
                type="button"
                onClick={() => {
                  onChange(month.year(year));
                  setOpen(false);
                }}
                className={`block h-8 w-full px-4 text-left text-[12px] ${
                  year === month.year()
                    ? 'bg-[var(--theme-accent-soft)] font-semibold text-[var(--theme-accent)]'
                    : 'text-slate-600 hover:bg-slate-50'
                }`}
              >
                {year}年
              </button>
            ))}
          </div>
        </AnchoredPopover>
      </div>
    </div>
  );
}

function MonthTabs({ month, onChange }: { month: Dayjs; onChange: (value: Dayjs) => void }) {
  const visibleMonths = month.year() === dayjs().year() ? Math.min(12, dayjs().month() + 2) : 12;
  return (
    <div className="mt-0 flex h-11 items-end gap-0 overflow-x-auto border-b border-[#eef2f7]">
      {Array.from({ length: visibleMonths }, (_, index) => index + 1).map((value) => {
        const active = month.month() === value - 1;
        return (
          <button
            key={value}
            type="button"
            onClick={() => onChange(month.month(value - 1))}
            className={`relative flex h-11 w-11 shrink-0 items-center justify-center text-[12px] leading-none transition-colors ${
              active
                ? 'font-semibold text-[var(--theme-accent)]'
                : 'font-normal text-slate-400 hover:text-slate-600'
            }`}
          >
            {value}月
            {active && (
              <span className="absolute inset-x-2 bottom-0 h-[2px] rounded-full bg-[var(--theme-accent)]" />
            )}
          </button>
        );
      })}
    </div>
  );
}

function NewObjectiveForm({
  index,
  submitting,
  onCancel,
  onSubmit,
}: {
  index: number;
  submitting: boolean;
  onCancel: () => void;
  onSubmit: (title: string) => void;
}) {
  const [title, setTitle] = useState('');
  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    const value = title.trim();
    if (!value || submitting) return;
    onSubmit(value);
  };

  return (
    <section className="workspace-card overflow-hidden">
      <div className="flex h-[49px] items-center gap-3 px-4">
        <span className="flex h-7 min-w-8 items-center justify-center rounded-full bg-[var(--theme-accent-soft)] px-2 text-[11px] font-semibold text-[var(--theme-accent)]">O{index}</span>
        <span className="min-w-0 flex-1 text-xs font-medium text-slate-400">输入目标描述...</span>
        <span className="text-[11px] font-medium text-red-500">0%</span>
      </div>
      <form onSubmit={handleSubmit} className="flex items-center gap-3 border-t border-slate-100 bg-slate-50/50 px-4 py-3">
        <input
          autoFocus
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          placeholder="输入目标描述..."
          className="h-10 min-w-0 flex-1 rounded-xl border border-[#cfdbea] bg-white px-4 text-xs text-slate-800 outline-none placeholder:text-slate-400 focus:border-[var(--theme-accent)]"
        />
        <button type="button" onClick={onCancel} className="h-9 min-w-[64px] rounded-xl border border-[#d7e0ec] bg-white px-4 text-xs text-slate-500">取消</button>
        <button type="submit" disabled={!title.trim() || submitting} className="h-9 min-w-[64px] rounded-xl bg-[var(--theme-accent)] px-4 text-xs font-semibold text-white hover:bg-[var(--theme-accent-hover)] disabled:opacity-40">
          {submitting ? '提交中…' : '确认'}
        </button>
      </form>
    </section>
  );
}
