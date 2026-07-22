import { Check, ChevronLeft, ChevronRight, Lock, Plus } from 'lucide-react';
import { cnWeekday, toApiDate, weekDates, type Dayjs } from '@/lib/date';
import type { DailyRangeDayOut, DailyTaskOut } from '@/types/api';
import type { CalendarView } from '@/components/date/DateWeekPicker';

interface TaskCalendarProps {
  view: Exclude<CalendarView, 'day'>;
  selected: Dayjs;
  days: DailyRangeDayOut[];
  loading: boolean;
  onNavigate: (day: Dayjs) => void;
  onSelectDay: (day: Dayjs) => void;
  onAdd: (day: Dayjs) => void;
}

const WEEKDAY_LABELS = ['周一', '周二', '周三', '周四', '周五', '周六', '周日'];

export default function TaskCalendar({
  view,
  selected,
  days,
  loading,
  onNavigate,
  onSelectDay,
  onAdd,
}: TaskCalendarProps) {
  const tasksByDate = new Map(days.map((item) => [item.date, item.tasks]));
  const shift = (amount: number) => {
    onNavigate(view === 'week' ? selected.add(amount, 'week') : selected.add(amount, 'month'));
  };

  return (
    <div className="border-b border-slate-100 px-3 pb-3 pt-2 sm:px-4">
      <div className="flex h-10 items-center justify-between gap-3">
        <button type="button" onClick={() => shift(-1)} className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200 text-slate-400 hover:border-slate-300 hover:text-slate-700" aria-label={view === 'week' ? '上一周' : '上个月'}>
          <ChevronLeft size={15} />
        </button>
        <strong className="text-[12px] font-semibold text-slate-800">
          {view === 'week'
            ? `${weekDates(selected)[0].format('M.D')} - ${weekDates(selected)[6].format('M.D')}`
            : selected.format('YYYY年M月')}
        </strong>
        <button type="button" onClick={() => shift(1)} className="flex h-7 w-7 items-center justify-center rounded-lg border border-slate-200 text-slate-400 hover:border-slate-300 hover:text-slate-700" aria-label={view === 'week' ? '下一周' : '下个月'}>
          <ChevronRight size={15} />
        </button>
      </div>

      {loading ? (
        <div className="flex h-32 items-center justify-center text-xs text-slate-400">正在加载工作清单…</div>
      ) : view === 'week' ? (
        <WeekBoard
          selected={selected}
          tasksByDate={tasksByDate}
          onSelect={onSelectDay}
          onAdd={onAdd}
        />
      ) : (
        <MonthBoard
          selected={selected}
          tasksByDate={tasksByDate}
          onSelect={onSelectDay}
          onAdd={onAdd}
        />
      )}

      <p className="mt-2 text-[10px] leading-4 text-slate-400">
        {view === 'week'
          ? '点击日期切换下方详情；每日/每周循环任务会在对应日期自动出现，未来日期不会提前补齐。'
          : '绿色为空档，黄色为 1–2 件，红色为 3 件及以上；点击日期查看完整内容，点击加号直接添加。'}
      </p>
    </div>
  );
}

function WeekBoard({
  selected,
  tasksByDate,
  onSelect,
  onAdd,
}: {
  selected: Dayjs;
  tasksByDate: Map<string, DailyTaskOut[]>;
  onSelect: (day: Dayjs) => void;
  onAdd: (day: Dayjs) => void;
}) {
  return (
    <div className="overflow-x-auto pb-1">
      <div className="grid min-w-[980px] grid-cols-7 gap-2">
        {weekDates(selected).map((day) => {
          const key = toApiDate(day);
          const tasks = tasksByDate.get(key) ?? [];
          const active = day.isSame(selected, 'day');
          return (
            <div
              key={key}
              onClick={() => onSelect(day)}
              className={`daily-week-card flex cursor-pointer flex-col rounded-xl border p-2.5 transition-colors ${active ? 'border-[var(--theme-accent)] bg-[var(--theme-accent-soft)] shadow-sm' : 'border-slate-200 bg-slate-50/60 hover:border-slate-300'}`}
            >
              <div className="flex items-center justify-between">
                <strong className="text-[11px] text-slate-700">{cnWeekday(day)} {day.date()}</strong>
                <span className="text-[10px] text-slate-300">{tasks.length ? `${tasks.length}件` : '空'}</span>
              </div>
              <div className="mt-2 flex-1 space-y-1">
                {tasks.slice(0, 4).map((task) => (
                  <TaskChip key={task.id} task={task} onClick={() => onSelect(day)} />
                ))}
                {tasks.length > 4 && <p className="px-1 text-[10px] text-slate-400">还有 {tasks.length - 4} 件…</p>}
              </div>
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation();
                  onAdd(day);
                }}
                className="mt-2 flex h-7 items-center justify-center gap-1 rounded-lg border border-dashed border-slate-200 text-[10px] text-slate-400 hover:border-[var(--theme-accent)] hover:text-[var(--theme-accent)]"
              >
                <Plus size={11} />添加
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function MonthBoard({
  selected,
  tasksByDate,
  onSelect,
  onAdd,
}: {
  selected: Dayjs;
  tasksByDate: Map<string, DailyTaskOut[]>;
  onSelect: (day: Dayjs) => void;
  onAdd: (day: Dayjs) => void;
}) {
  const start = selected.startOf('month').startOf('isoWeek');
  const end = selected.endOf('month').endOf('isoWeek');
  const count = end.diff(start, 'day') + 1;
  const calendarDays = Array.from({ length: count }, (_, index) => start.add(index, 'day'));

  return (
    <div className="overflow-x-auto pb-1">
      <div className="min-w-[860px]">
        <div className="grid grid-cols-7">
          {WEEKDAY_LABELS.map((label) => <div key={label} className="py-2 text-center text-[10px] text-slate-400">{label}</div>)}
        </div>
        <div className="grid grid-cols-7 gap-1.5">
          {calendarDays.map((day) => {
            const key = toApiDate(day);
            const tasks = tasksByDate.get(key) ?? [];
            const inMonth = day.month() === selected.month();
            const active = day.isSame(selected, 'day');
            const tone = !inMonth
              ? 'border-transparent bg-slate-50/40 text-slate-300'
              : tasks.length >= 3
                ? 'border-rose-200 bg-rose-50/70'
                : tasks.length > 0
                  ? 'border-amber-200 bg-amber-50/70'
                  : 'border-emerald-200 bg-emerald-50/65';
            return (
              <div
                key={key}
                onClick={() => onSelect(day)}
                className={`daily-month-card cursor-pointer rounded-xl border p-2 transition-colors ${tone} ${active ? 'ring-2 ring-inset ring-[var(--theme-accent)]' : 'hover:border-slate-300'}`}
              >
                <div className="flex items-center justify-between">
                  <span className={`text-[11px] font-medium ${inMonth ? 'text-slate-700' : 'text-slate-300'}`}>{day.date()}</span>
                  {inMonth && (
                    <div className="flex items-center gap-1.5">
                      <span className="text-[9px] text-slate-400">{tasks.length ? `${tasks.filter((task) => task.is_done).length}/${tasks.length}` : '空'}</span>
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          onAdd(day);
                        }}
                        className="text-slate-400 hover:text-[var(--theme-accent)]"
                        aria-label={`${day.format('M月D日')}添加事项`}
                      >
                        <Plus size={12} />
                      </button>
                    </div>
                  )}
                </div>
                {inMonth && (
                  <div className="mt-1.5 space-y-1">
                    {tasks.slice(0, 3).map((task) => <TaskChip key={task.id} task={task} onClick={() => onSelect(day)} compact />)}
                    {tasks.length > 3 && <p className="px-1 text-[9px] text-slate-400">+{tasks.length - 3} 件</p>}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function TaskChip({ task, onClick, compact = false }: { task: DailyTaskOut; onClick: () => void; compact?: boolean }) {
  return (
    <button
      type="button"
      onClick={(event) => {
        event.stopPropagation();
        onClick();
      }}
      className={`flex w-full items-center gap-1 rounded-lg border border-white/80 bg-white/90 px-1.5 text-left shadow-sm ${compact ? 'h-6 text-[9px]' : 'min-h-7 py-1 text-[10px]'}`}
      title={task.content}
    >
      {task.is_done ? <Check size={10} className="shrink-0 text-emerald-600" /> : <span className="h-2 w-2 shrink-0 rounded-full bg-slate-200" />}
      <span className="shrink-0 font-mono text-slate-400">{task.task_time.slice(0, 5)}</span>
      <span className={`min-w-0 flex-1 truncate ${task.is_done ? 'text-slate-400 line-through' : 'text-slate-700'}`}>{task.content}</span>
      {task.is_private && <Lock size={9} className="shrink-0 text-slate-400" />}
    </button>
  );
}
