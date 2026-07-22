import { Calendar as CalendarIcon, HelpCircle, Lightbulb } from 'lucide-react';
import { dayjs, type Dayjs, cnWeekday, toApiDate, weekDates } from '@/lib/date';

export type CalendarView = 'day' | 'week' | 'month';

interface DateWeekPickerProps {
  selected: Dayjs;
  onSelect: (date: Dayjs) => void;
  view?: CalendarView;
  onViewChange?: (view: CalendarView) => void;
  // Hide the 灵感清单 button and the help hint — used by read-only views
  // (e.g. the subscription pages) that only need the date jump control.
  hideExtras?: boolean;
}

export default function DateWeekPicker({
  selected,
  onSelect,
  view = 'day',
  onViewChange,
  hideExtras = false,
}: DateWeekPickerProps) {
  const days = weekDates(selected);
  const selectedKey = toApiDate(selected);
  const todayKey = toApiDate(dayjs());
  return (
    <div className="flex min-h-[3.375rem] flex-wrap items-center justify-between gap-4 px-2">
      <div className="flex min-w-0 items-center gap-1 overflow-x-auto pb-1">
        {days.map((day) => {
          const key = toApiDate(day);
          const active = key === selectedKey;
          const today = key === todayKey;
          const stateClass = today
            ? active
              ? 'border-[var(--theme-accent)] bg-[var(--theme-accent)] font-semibold text-white shadow-sm'
              : 'border-[var(--theme-accent)] bg-[var(--theme-accent-soft)] font-semibold text-[var(--theme-accent)]'
            : active
              ? 'border-slate-200 bg-white font-medium text-slate-900 shadow-sm'
              : 'border-transparent text-slate-500 hover:bg-white';
          return (
            <button
              key={key}
              type="button"
              aria-current={today ? 'date' : undefined}
              onClick={() => {
                onSelect(day);
                onViewChange?.('day');
              }}
              className={`relative flex h-[3.375rem] w-[3.625rem] shrink-0 flex-col items-center justify-center rounded-[0.625rem] border transition-colors ${stateClass}`}
            >
              <span className="h-4 text-xs leading-4 opacity-75">{cnWeekday(day)}</span>
              <span className="mt-0.5 h-[1.125rem] text-[0.8125rem] font-semibold leading-[1.125rem]">{day.format('M.D')}</span>
            </button>
          );
        })}
        <div className="ml-1 flex items-center gap-1">
          {(['week', 'month'] as const).map((item) => (
            <button
              key={item}
              type="button"
              onClick={() => onViewChange?.(item)}
              className={`flex h-[3.375rem] w-12 shrink-0 flex-col items-center justify-center rounded-[0.625rem] transition-colors ${view === item ? 'bg-[var(--theme-accent)] font-semibold text-white shadow-sm' : 'text-slate-500 hover:bg-white'}`}
            >
              <span className="h-4 text-xs font-normal leading-4 opacity-75">视图</span>
              <strong className="mt-0.5 h-[1.125rem] text-[0.8125rem] font-semibold leading-[1.125rem]">{item === 'week' ? '周' : '月'}</strong>
            </button>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <label className="workspace-button h-10 cursor-pointer border-slate-400 text-slate-700">
          <CalendarIcon size={14} className="theme-icon-color" />
          <input
            type="date"
            value={selectedKey}
            onChange={(event) => {
              if (!event.target.value) return;
              onSelect(dayjs(event.target.value));
              onViewChange?.('day');
            }}
            className="w-[102px] bg-transparent text-xs outline-none"
          />
        </label>
        {!hideExtras && (
          <>
            <button disabled title="功能预留，暂未开放" className="workspace-button h-10 cursor-not-allowed border-amber-100 bg-amber-50/60 text-amber-500 opacity-75"><Lightbulb size={14} />灵感清单</button>
            <HelpCircle size={14} className="text-slate-300" />
          </>
        )}
      </div>
    </div>
  );
}
