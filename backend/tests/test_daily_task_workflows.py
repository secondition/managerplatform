from __future__ import annotations

from datetime import date, time

from sqlalchemy import select

from app.models.daily import DailyReport, DailyTask, DailyTaskCollaborator
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.daily import DailyTaskCreate, DailyTaskUpdate
from app.services.ai_service import AiService
from app.services.daily_service import DailyService
from app.services.people_service import PeopleService
from app.services.subscription_service import SubscriptionService


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


def test_daily_tasks_are_returned_in_time_order(db, user):
    service = DailyService(db, user)
    for task_time, content in (
        (time(16, 0), "下午事项"),
        (time(9, 30), "上午事项"),
        (time(9, 0), "最早事项"),
    ):
        service.create_task(
            DailyTaskCreate(
                date=date(2026, 7, 20),
                task_time=task_time,
                content=content,
            )
        )

    result = service.get_own_daily_out(date(2026, 7, 20))

    assert [task.content for task in result.tasks] == ["最早事项", "上午事项", "下午事项"]


def test_daily_range_returns_owned_and_collaborative_tasks_by_date(db, user):
    colleague = _user(db, "range-colleague")
    service = DailyService(db, user)
    service.create_task(
        DailyTaskCreate(
            date=date(2026, 7, 20),
            task_time=time(14, 0),
            content="周一事项",
        )
    )
    service.create_task(
        DailyTaskCreate(
            date=date(2026, 7, 22),
            task_time=time(9, 0),
            content="周三事项",
        )
    )
    DailyService(db, colleague).create_task(
        DailyTaskCreate(
            date=date(2026, 7, 21),
            task_time=time(10, 0),
            content="协作事项",
            collaborator_ids=[user.id],
            is_private=True,
        )
    )

    result = service.get_own_range_out(date(2026, 7, 20), date(2026, 7, 22))

    assert [item.date for item in result] == [
        date(2026, 7, 20),
        date(2026, 7, 21),
        date(2026, 7, 22),
    ]
    assert [[task.content for task in item.tasks] for item in result] == [
        ["周一事项"],
        ["协作事项"],
        ["周三事项"],
    ]
    assert result[1].tasks[0].permission == "collaborator"
    assert result[1].tasks[0].is_private is True


def test_private_task_is_hidden_from_followers_but_visible_to_participants(db, user):
    collaborator = _user(db, "private-collaborator")
    follower = _user(db, "private-follower")
    service = DailyService(db, user)
    private_task = service.create_task(
        DailyTaskCreate(
            date=date(2026, 7, 20),
            task_time=time(9, 0),
            content="私人事项",
            collaborator_ids=[collaborator.id],
            is_private=True,
        )
    )
    service.create_task(
        DailyTaskCreate(
            date=date(2026, 7, 20),
            task_time=time(10, 0),
            content="公开事项",
        )
    )
    service.create_task(
        DailyTaskCreate(
            date=date(2026, 7, 17),
            task_time=time(9, 0),
            content="仅私人日期事项",
            is_private=True,
        )
    )

    owner_view = service.get_own_daily_out(date(2026, 7, 20))
    collaborator_view = DailyService(db, collaborator).get_own_daily_out(date(2026, 7, 20))
    subscription_service = SubscriptionService(db, follower)
    subscription_service.subscribe_daily(user.id)
    follower_view = subscription_service.get_daily_report(user.id, date(2026, 7, 20))

    assert [task.content for task in owner_view.tasks] == ["私人事项", "公开事项"]
    assert owner_view.tasks[0].is_private is True
    assert [task.id for task in collaborator_view.tasks] == [private_task.id]
    assert collaborator_view.tasks[0].permission == "collaborator"
    assert [task.content for task in follower_view.tasks] == ["公开事项"]

    follower_context = AiService(db, follower)._company_text_snippets(
        date(2026, 7, 20), follower
    )
    owner_context = AiService(db, user)._company_text_snippets(
        date(2026, 7, 20), user
    )
    assert "私人事项" not in follower_context
    assert "私人事项" in owner_context

    owner_calendar = PeopleService(db, user)._daily_calendar(user.id, "2026-07")
    follower_calendar = PeopleService(db, follower)._daily_calendar(user.id, "2026-07")
    owner_private_day = next(day for day in owner_calendar.days if day.date == date(2026, 7, 17))
    follower_private_day = next(
        day for day in follower_calendar.days if day.date == date(2026, 7, 17)
    )
    assert owner_private_day.has_daily is True
    assert follower_private_day.has_daily is False


def test_edit_can_dispatch_with_repeat_collaborators_and_privacy(db, user):
    assignee = _user(db, "edit-assignee")
    collaborator = _user(db, "edit-collaborator")
    service = DailyService(db, user)
    original = service.create_task(
        DailyTaskCreate(
            date=date(2026, 7, 20),
            task_time=time(9, 0),
            content="原事项",
        )
    )

    dispatched = service.update_task(
        original.id,
        DailyTaskUpdate(
            task_time=time(11, 30),
            content="编辑后派发",
            note="需要共同处理",
            repeat_rule="weekly",
            collaborator_ids=[collaborator.id],
            assigned_to_ids=[assignee.id],
            is_private=True,
        ),
    )

    db.refresh(original)
    assert original.deleted_at is not None
    assert dispatched.user_id == assignee.id
    assert dispatched.assigned_to == assignee.id
    assert dispatched.assigned_by == user.id
    assert dispatched.source == "assigned"
    assert dispatched.task_time == time(11, 30)
    assert dispatched.content == "编辑后派发"
    assert dispatched.note == "需要共同处理"
    assert dispatched.repeat_rule == "weekly"
    assert dispatched.is_private is True
    assert db.scalar(
        select(DailyTaskCollaborator.user_id).where(
            DailyTaskCollaborator.task_id == dispatched.id,
            DailyTaskCollaborator.deleted_at.is_(None),
        )
    ) == collaborator.id

    future = db.scalar(
        select(DailyTask)
        .join(DailyReport, DailyReport.id == DailyTask.report_id)
        .where(
            DailyTask.repeat_series_id == dispatched.repeat_series_id,
            DailyTask.id != dispatched.id,
            DailyTask.deleted_at.is_(None),
        )
    )
    assert future is not None
    assert future.user_id == assignee.id
    assert future.is_private is True
    assert db.scalar(
        select(DailyTaskCollaborator.user_id).where(
            DailyTaskCollaborator.task_id == future.id,
            DailyTaskCollaborator.deleted_at.is_(None),
        )
    ) == collaborator.id

    subscription = db.scalar(
        select(Subscription).where(
            Subscription.subscriber_id == user.id,
            Subscription.target_user_id == assignee.id,
            Subscription.deleted_at.is_(None),
        )
    )
    assert subscription is not None
    assert subscription.daily_enabled is True
    assert SubscriptionService(db, user).get_daily_report(
        assignee.id, date(2026, 7, 20)
    ).tasks == []


def test_edit_enabling_repeat_copies_new_collaborators(db, user):
    collaborator = _user(db, "new-repeat-collaborator")
    service = DailyService(db, user)
    task = service.create_task(
        DailyTaskCreate(
            date=date(2026, 7, 20),
            task_time=time(9, 0),
            content="单次事项",
        )
    )

    updated = service.update_task(
        task.id,
        DailyTaskUpdate(
            repeat_rule="daily",
            collaborator_ids=[collaborator.id],
            is_private=True,
        ),
    )
    future = db.scalar(
        select(DailyTask)
        .where(
            DailyTask.repeat_series_id == updated.repeat_series_id,
            DailyTask.id != updated.id,
            DailyTask.deleted_at.is_(None),
        )
    )

    assert future is not None
    assert future.is_private is True
    assert db.scalar(
        select(DailyTaskCollaborator.user_id).where(
            DailyTaskCollaborator.task_id == future.id,
            DailyTaskCollaborator.deleted_at.is_(None),
        )
    ) == collaborator.id
