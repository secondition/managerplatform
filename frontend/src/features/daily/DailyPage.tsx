import { useState } from 'react';
import { AlertCircle, Check, Lightbulb, RefreshCw, X } from 'lucide-react';
import { dayjs, type Dayjs, toApiDate } from '@/lib/date';
import Spinner from '@/components/ui/Spinner';
import DateWeekPicker, { type CalendarView } from '@/components/date/DateWeekPicker';
import { useDailyReport } from './hooks';
import { useAiFeatureFlags } from './aiHooks';
import { TodaySuggestion, AiScorePanel } from './AiPlaceholders';
import TaskList from './TaskList';
import TaskCalendar from './TaskCalendar';
import ProblemList from './ProblemList';
import type { DailyRangeDayOut, DailyTaskOut } from '@/types/api';
import { useDailyRange } from './hooks';

const PREVIEW_DATE = '2026-07-20';

const PREVIEW_TASKS: DailyTaskOut[] = [
  {
    id: 9002,
    report_id: 9000,
    user_id: 1,
    task_time: '14:00:00',
    content: '复盘本周客户转化数据',
    note: '整理异常渠道和后续动作',
    is_private: false,
    is_done: false,
    done_at: null,
    repeat_rule: 'weekly',
    source: 'manual',
    assigned_to: null,
    assigned_by: null,
    sort_order: 1,
    collaborators: [],
    permission: 'owner',
    can_edit: true,
    can_delete: true,
    can_toggle_done: true,
    can_manage_members: true,
  },
  {
    id: 9001,
    report_id: 9000,
    user_id: 1,
    task_time: '09:30:00',
    content: '完成供应商报价确认',
    note: null,
    is_private: true,
    is_done: true,
    done_at: '2026-07-20T10:15:00',
    repeat_rule: 'none',
    source: 'manual',
    assigned_to: null,
    assigned_by: null,
    sort_order: 2,
    collaborators: [],
    permission: 'owner',
    can_edit: true,
    can_delete: true,
    can_toggle_done: true,
    can_manage_members: true,
  },
];

export default function DailyPage() {
  const preview = import.meta.env.DEV && new URLSearchParams(window.location.search).get('preview') === '1';
  const [selected, setSelected] = useState<Dayjs>(() => dayjs());
  const [view, setView] = useState<CalendarView>('day');
  const [addRequest, setAddRequest] = useState(0);
  const date = toApiDate(selected);
  const rangeStart = view === 'month'
    ? selected.startOf('month').startOf('isoWeek')
    : selected.startOf('isoWeek');
  const rangeEnd = view === 'month'
    ? selected.endOf('month').endOf('isoWeek')
    : selected.endOf('isoWeek');
  const rangeStartKey = toApiDate(rangeStart);
  const rangeEndKey = toApiDate(rangeEnd);

  const report = useDailyReport(date);
  const range = useDailyRange(rangeStartKey, rangeEndKey, view !== 'day');
  const flags = useAiFeatureFlags();
  const rangeDays = preview
    ? previewRange(rangeStart, rangeEnd)
    : range.data ?? [];
  const selectedTasks = report.data?.tasks ?? (preview && date === PREVIEW_DATE ? PREVIEW_TASKS : []);

  const requestAdd = (day: Dayjs) => {
    setSelected(day);
    setView('day');
    setAddRequest((value) => value + 1);
  };

  const openDay = (day: Dayjs) => {
    setSelected(day);
    setView('day');
  };

  return (
    <div className="workspace-page space-y-5">
      <DateWeekPicker
        selected={selected}
        onSelect={setSelected}
        view={view}
        onViewChange={setView}
      />

      {view === 'day' && flags.data?.daily_suggestion_enabled && <TodaySuggestion date={date} />}
      {view === 'day' && preview && !flags.data && <PreviewSuggestions />}

      {view !== 'day' ? (
        <TaskList
          date={date}
          tasks={[]}
          calendar={(
            <TaskCalendar
              view={view}
              selected={selected}
              days={rangeDays}
              loading={range.isLoading && !preview}
              onNavigate={setSelected}
              onSelectDay={openDay}
              onAdd={requestAdd}
            />
          )}
          calendarOnly
          calendarLabel={view === 'week' ? '周视图' : '月视图'}
        />
      ) : report.isLoading && !preview ? (
        <Spinner label="正在加载日报…" />
      ) : report.isError && !preview ? (
        <div className="flex items-center gap-2 rounded-xl bg-red-50 border border-red-100 px-4 py-3 text-xs text-red-600">
          <AlertCircle size={14} />
          加载日报失败，请稍后重试。
        </div>
      ) : (
        <>
          <TaskList
            date={date}
            tasks={selectedTasks}
            addRequest={addRequest}
          />
          <ProblemList date={date} problems={report.data?.problems ?? []} />
        </>
      )}

      {view === 'day' && (flags.data?.daily_score_enabled || preview) && <AiScorePanel date={date} />}
    </div>
  );
}

function previewRange(start: Dayjs, end: Dayjs): DailyRangeDayOut[] {
  const count = end.diff(start, 'day') + 1;
  return Array.from({ length: count }, (_, index) => {
    const date = toApiDate(start.add(index, 'day'));
    return { date, tasks: date === PREVIEW_DATE ? PREVIEW_TASKS : [] };
  });
}

function PreviewSuggestions() {
  const suggestions = [
    { type: '推进', className: 'bg-amber-50 text-amber-700', text: '草拟运营SOP撰写模板与示例，确保统一格式' },
    { type: '协作', className: 'bg-blue-50 text-blue-600', text: '召集运营委员会成员开启启动会，明确分工和截止日' },
    { type: '推进', className: 'bg-amber-50 text-amber-700', text: '制定从撰写到评审的倒排计划表，锁定关键节点' },
  ];
  return <div className="workspace-card overflow-hidden"><div className="flex h-[3.25rem] items-center justify-between px-5"><strong className="flex items-center gap-2 text-sm font-semibold text-slate-900"><Lightbulb size={16} className="theme-icon-color" />今日建议</strong><button className="flex items-center gap-1.5 text-xs text-[var(--theme-accent)] hover:opacity-80"><RefreshCw size={13} />重新建议</button></div>{suggestions.map((suggestion) => <div key={suggestion.text} className="flex min-h-[2.5625rem] items-center gap-3 border-t border-slate-100 px-5 py-1.5"><span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${suggestion.className}`}>{suggestion.type}</span><span className="min-w-0 flex-1 truncate text-xs font-medium text-slate-800">{suggestion.text}</span><button className="flex h-7 items-center gap-1 rounded-md bg-[var(--theme-accent)] px-3 text-xs font-medium text-white shadow-sm hover:bg-[var(--theme-accent-hover)]"><Check size={13} />确认</button><button className="flex items-center gap-1 text-xs text-slate-500"><X size={13} />取消</button></div>)}</div>;
}
