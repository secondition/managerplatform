from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class WeekColumn:
    week_index: int
    label: str
    week_start: date | None
    week_end: date | None
    is_empty: bool


def parse_month(month: str) -> tuple[int, int]:
    parts = month.split("-")
    if len(parts) != 2:
        raise ValueError("month must be YYYY-MM")
    year, month_num = int(parts[0]), int(parts[1])
    if month_num < 1 or month_num > 12:
        raise ValueError("month must be YYYY-MM")
    return year, month_num


def month_bounds(month: str) -> tuple[date, date]:
    year, month_num = parse_month(month)
    _, last_day = calendar.monthrange(year, month_num)
    return date(year, month_num, 1), date(year, month_num, last_day)


def week_columns(month: str) -> list[WeekColumn]:
    month_start, month_end = month_bounds(month)
    current = week_start_for(month_start)
    columns: list[WeekColumn] = []

    index = 0
    while current <= month_end:
        end = current + timedelta(days=6)
        columns.append(WeekColumn(index, f"W{index}", current, end, False))
        index += 1
        current += timedelta(days=7)

    return columns


def recent_weeks(end_week_start: date, count: int) -> list[WeekColumn]:
    """A rolling window of ``count`` consecutive Monday-start weeks.

    ``end_week_start`` is the Monday of the newest (rightmost) week in the
    window; the window spans backwards from there. Labels are absolute ISO week
    numbers (e.g. ``W28``) since metrics are no longer month-scoped.
    """
    if count < 1:
        return []
    anchor = week_start_for(end_week_start)
    columns: list[WeekColumn] = []
    for offset in range(count - 1, -1, -1):
        start = anchor - timedelta(days=7 * offset)
        end = start + timedelta(days=6)
        iso_week = start.isocalendar().week
        columns.append(WeekColumn(iso_week, f"W{iso_week}", start, end, False))
    return columns


def last_completed_week_start(today: date) -> date:
    """Monday of the most recently *finished* week relative to ``today``.

    A new week becomes fillable the following Monday, so the newest column is
    always the week that has already ended.
    """
    this_week_monday = week_start_for(today)
    return this_week_monday - timedelta(days=7)


def week_start_for(value: date) -> date:
    return value - timedelta(days=value.weekday())


def week_dates(value: date) -> list[date]:
    start = week_start_for(value)
    return [start + timedelta(days=offset) for offset in range(7)]


def working_days_in(start: date, end: date) -> int:
    """Count Mon–Fri days in the inclusive [start, end] range."""
    if end < start:
        return 0
    count = 0
    current = start
    while current <= end:
        if current.weekday() < 5:  # 0=Mon .. 4=Fri
            count += 1
        current += timedelta(days=1)
    return count
