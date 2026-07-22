import { ChevronLeft, ChevronRight } from 'lucide-react';
import { dayjs, type Dayjs, toApiDate } from '@/lib/date';

interface WeekPagerProps {
  // Monday of the newest week in the window, or null = latest completed week.
  anchor: Dayjs | null;
  count: number;
  onChange: (anchor: Dayjs | null) => void;
}

// Monday of the most recently *completed* week (a week becomes fillable the
// following Monday), matching the backend's last_completed_week_start.
function lastCompletedMonday(): Dayjs {
  return dayjs().startOf('isoWeek').subtract(7, 'day');
}

// Pages the rolling window by whole pages of `count` weeks.
export default function WeekPager({ anchor, count, onChange }: WeekPagerProps) {
  const latest = lastCompletedMonday();
  const current = anchor ?? latest;
  const isLatest = current.isSame(latest, 'day') || current.isAfter(latest, 'day');

  const windowStart = current.subtract((count - 1) * 7, 'day');
  const label = `${windowStart.format('M.D')} – ${current.add(6, 'day').format('M.D')}`;

  const goOlder = () => onChange(current.subtract(count * 7, 'day'));
  const goNewer = () => {
    const next = current.add(count * 7, 'day');
    onChange(next.isAfter(latest, 'day') ? null : next);
  };

  return (
    <div className="flex items-center gap-6 text-[13px]">
      <button
        onClick={goOlder}
        className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-[#d7e0ec] bg-white px-3 text-[13px] font-medium text-slate-600 shadow-[0_1px_2px_rgba(15,23,42,.03)] transition-colors hover:border-[var(--theme-accent)] hover:text-[var(--theme-accent)]"
        title={`更早 ${count} 周`}
      >
        <ChevronLeft size={15} />
        更早
      </button>
      <span className="min-w-[92px] text-center font-semibold text-slate-950 tabular-nums">
        {label}
      </span>
      <button
        onClick={goNewer}
        disabled={isLatest}
        className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-[#e5ebf3] bg-white px-3 text-[13px] font-medium text-slate-400 shadow-[0_1px_2px_rgba(15,23,42,.02)] transition-colors hover:border-[var(--theme-accent)] hover:text-[var(--theme-accent)] disabled:cursor-not-allowed disabled:border-[#edf1f6] disabled:text-slate-300"
        title={`更近 ${count} 周`}
      >
        更近
        <ChevronRight size={15} />
      </button>
      {!isLatest && (
        <button
          onClick={() => onChange(null)}
          className="text-[12px] text-[var(--theme-accent)] hover:text-[var(--theme-accent-hover)] font-medium cursor-pointer"
        >
          回到最近
        </button>
      )}
    </div>
  );
}

export function anchorToApi(anchor: Dayjs | null): string | null {
  return anchor ? toApiDate(anchor) : null;
}
