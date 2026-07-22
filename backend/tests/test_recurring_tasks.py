from __future__ import annotations

from datetime import date, time

from sqlalchemy import select

from app.models.daily import DailyReport, DailyTask, DailyTaskCollaborator
from app.models.user import User
from app.schemas.daily import DailyTaskCreate, DailyTaskUpdate
from app.services.daily_service import (
    DailyService,
    materialize_recurring_tasks,
    next_repeat_date,
)


def _user(db, suffix: str) -> User:
    user = User(
        name=f"User {suffix}",
        role="member",
        feishu_union_id=f"union-{suffix}",
        feishu_open_id=f"open-{suffix}",
        status="active",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _series_tasks(db, series_id: str) -> list[DailyTask]:
    return list(
        db.scalars(
            select(DailyTask)
            .join(DailyReport, DailyReport.id == DailyTask.report_id)
            .where(
                DailyTask.repeat_series_id == series_id,
                DailyTask.deleted_at.is_(None),
            )
            .order_by(DailyReport.report_date)
        ).all()
    )


def _report_date(db, task: DailyTask) -> date:
    return db.scalar(
        select(DailyReport.report_date).where(DailyReport.id == task.report_id)
    )


def test_next_repeat_date_skips_weekends():
    assert next_repeat_date(date(2026, 7, 10), "daily") == date(2026, 7, 13)
    assert next_repeat_date(date(2026, 7, 11), "daily") == date(2026, 7, 13)
    assert next_repeat_date(date(2026, 7, 10), "weekly") == date(2026, 7, 17)
    assert next_repeat_date(date(2026, 7, 11), "weekly") == date(2026, 7, 20)


def test_create_daily_repeat_copies_task_and_collaborators(db, user):
    collaborator = _user(db, "repeat-collaborator")
    task = DailyService(db, user).create_task(
        DailyTaskCreate(
            date=date(2026, 7, 10),
            task_time=time(9, 30),
            content="跟进关键客户",
            note="每日检查进展",
            repeat_rule="daily",
            collaborator_ids=[collaborator.id],
        )
    )

    assert task.repeat_series_id is not None
    tasks = _series_tasks(db, task.repeat_series_id)
    assert [_report_date(db, item) for item in tasks] == [
        date(2026, 7, 10),
        date(2026, 7, 13),
    ]
    future = tasks[1]
    assert future.content == task.content
    assert future.note == task.note
    assert future.task_time == task.task_time
    assert future.repeat_rule == "daily"
    assert future.is_done is False
    assert db.scalar(
        select(DailyTaskCollaborator.user_id).where(
            DailyTaskCollaborator.task_id == future.id,
            DailyTaskCollaborator.deleted_at.is_(None),
        )
    ) == collaborator.id


def test_weekly_repeat_moves_weekend_occurrence_to_monday(db, user):
    task = DailyService(db, user).create_task(
        DailyTaskCreate(
            date=date(2026, 7, 11),
            task_time=time(10, 0),
            content="周度复盘",
            repeat_rule="weekly",
        )
    )

    tasks = _series_tasks(db, task.repeat_series_id)
    assert [_report_date(db, item) for item in tasks] == [
        date(2026, 7, 11),
        date(2026, 7, 20),
    ]


def test_materialization_keeps_one_future_occurrence_and_is_idempotent(db, user):
    task = DailyService(db, user).create_task(
        DailyTaskCreate(
            date=date(2026, 7, 9),
            task_time=time(9, 0),
            content="例行巡检",
            repeat_rule="daily",
        )
    )

    assert materialize_recurring_tasks(db, date(2026, 7, 10)) == 1
    assert materialize_recurring_tasks(db, date(2026, 7, 10)) == 0
    assert [_report_date(db, item) for item in _series_tasks(db, task.repeat_series_id)] == [
        date(2026, 7, 9),
        date(2026, 7, 10),
        date(2026, 7, 13),
    ]


def test_materialization_skips_expired_dates_after_downtime(db, user):
    report = DailyReport(
        user_id=user.id,
        report_date=date(2026, 7, 1),
        status="draft",
    )
    db.add(report)
    db.flush()
    task = DailyTask(
        report_id=report.id,
        user_id=user.id,
        task_time=time(9, 0),
        content="历史例行任务",
        repeat_rule="daily",
        repeat_series_id="legacy-series",
    )
    db.add(task)
    db.commit()

    assert materialize_recurring_tasks(db, date(2026, 7, 10)) == 2
    assert [_report_date(db, item) for item in _series_tasks(db, "legacy-series")] == [
        date(2026, 7, 1),
        date(2026, 7, 10),
        date(2026, 7, 13),
    ]


def test_updating_repeat_task_syncs_future_and_cancel_stops_series(db, user):
    task = DailyService(db, user).create_task(
        DailyTaskCreate(
            date=date(2026, 7, 9),
            task_time=time(9, 0),
            content="旧内容",
            repeat_rule="daily",
        )
    )
    series_id = task.repeat_series_id
    service = DailyService(db, user)
    service.update_task(
        task.id,
        DailyTaskUpdate(task_time=time(10, 0), content="新内容"),
    )
    future = _series_tasks(db, series_id)[1]
    assert future.task_time == time(10, 0)
    assert future.content == "新内容"

    service.update_task(task.id, DailyTaskUpdate(repeat_rule="none"))
    assert _series_tasks(db, series_id) == []
    db.refresh(task)
    assert task.repeat_rule == "none"
    assert task.repeat_series_id is None
    assert materialize_recurring_tasks(db, date(2026, 7, 20)) == 0


def test_deleting_repeat_task_prevents_older_occurrence_from_reviving_series(db, user):
    service = DailyService(db, user)
    first = service.create_task(
        DailyTaskCreate(
            date=date(2026, 7, 9),
            task_time=time(9, 0),
            content="日报整理",
            repeat_rule="daily",
        )
    )
    series_id = first.repeat_series_id
    second = _series_tasks(db, series_id)[1]
    service.delete_task(second.id)

    db.refresh(first)
    assert first.repeat_series_id is None
    assert _series_tasks(db, series_id) == []
    assert materialize_recurring_tasks(db, date(2026, 7, 20)) == 0
