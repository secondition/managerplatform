import dayjs, { type Dayjs } from 'dayjs';
import isoWeek from 'dayjs/plugin/isoWeek';

dayjs.extend(isoWeek);

export { dayjs };
export type { Dayjs };

// API date format used across daily/traffic endpoints.
export const API_DATE = 'YYYY-MM-DD';
export const API_MONTH = 'YYYY-MM';

export function toApiDate(value: Dayjs): string {
  return value.format(API_DATE);
}

export function toApiMonth(value: Dayjs): string {
  return value.format(API_MONTH);
}

// Monday-start week containing the anchor date (matches backend week_dates,
// which slices weeks from Monday in Asia/Shanghai).
export function weekDates(anchor: Dayjs): Dayjs[] {
  const monday = anchor.isoWeekday(1);
  return Array.from({ length: 7 }, (_, i) => monday.add(i, 'day'));
}

const CN_WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日'];

export function cnWeekday(value: Dayjs): string {
  // isoWeekday: 1 = Monday ... 7 = Sunday
  return `周${CN_WEEKDAYS[value.isoWeekday() - 1]}`;
}
