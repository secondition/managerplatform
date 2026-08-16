from __future__ import annotations

from datetime import date, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.daily import DailyReport, DailyTask, DailyTaskCollaborator, ProblemSolution
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.daily import (
    DailyTaskCreate,
    DailyTaskDoneIn,
    DailyTaskOut,
    DailyTaskUpdate,
    DailyRangeDayOut,
    DailyReportOut,
    ProblemSolutionCreate,
    ProblemSolutionUpdate,
)
from app.schemas.user import UserBrief
from app.services.notification_service import NotificationService
from app.utils.dates import week_dates
from app.utils.html_sanitize import extract_text, sanitize_html
from app.core.security import utcnow


def next_repeat_date(current: date, repeat_rule: str) -> date:
    if repeat_rule == "daily":
        next_date = current + timedelta(days=1)
    elif repeat_rule == "weekly":
        next_date = current + timedelta(days=7)
    else:
        raise ValueError("repeat_rule must be daily or weekly")
    while next_date.weekday() >= 5:
        next_date += timedelta(days=1)
    return next_date


def _get_or_create_repeat_report(
    db: Session, user_id: int, report_date: date, actor_id: int | None
) -> DailyReport:
    report = db.scalar(
        select(DailyReport).where(
            DailyReport.user_id == user_id,
            DailyReport.report_date == report_date,
            DailyReport.deleted_at.is_(None),
        )
    )
    if report is None:
        report = DailyReport(
            user_id=user_id,
            report_date=report_date,
            status="draft",
            created_by=actor_id,
            updated_by=actor_id,
        )
        db.add(report)
        db.flush()
    return report


def _create_next_repeat_occurrence(
    db: Session,
    task: DailyTask,
    current_date: date,
    occurrence_date: date | None = None,
) -> DailyTask | None:
    if task.repeat_rule not in {"daily", "weekly"} or not task.repeat_series_id:
        return None
    next_date = occurrence_date or next_repeat_date(current_date, task.repeat_rule)
    report = _get_or_create_repeat_report(db, task.user_id, next_date, task.created_by)
    existing = db.scalar(
        select(DailyTask).where(
            DailyTask.repeat_series_id == task.repeat_series_id,
            DailyTask.report_id == report.id,
            DailyTask.deleted_at.is_(None),
        )
    )
    if existing is not None:
        return existing
    next_sort = db.scalar(
        select(func.max(DailyTask.sort_order)).where(
            DailyTask.report_id == report.id,
            DailyTask.deleted_at.is_(None),
        )
    )
    clone = DailyTask(
        report_id=report.id,
        user_id=task.user_id,
        task_time=task.task_time,
        content=task.content,
        note=task.note,
        is_private=task.is_private,
        repeat_rule=task.repeat_rule,
        repeat_series_id=task.repeat_series_id,
        source=task.source,
        assigned_to=task.assigned_to,
        assigned_by=task.assigned_by,
        sort_order=(int(next_sort) + 1) if next_sort is not None else 0,
        created_by=task.created_by,
        updated_by=task.updated_by,
    )
    db.add(clone)
    db.flush()
    collaborator_ids = db.scalars(
        select(DailyTaskCollaborator.user_id).where(
            DailyTaskCollaborator.task_id == task.id,
            DailyTaskCollaborator.deleted_at.is_(None),
        )
    ).all()
    for collaborator_id in collaborator_ids:
        db.add(
            DailyTaskCollaborator(
                task_id=clone.id,
                user_id=collaborator_id,
                created_by=task.created_by,
                updated_by=task.updated_by,
            )
        )
    db.flush()
    return clone


def materialize_recurring_tasks(db: Session, through_date: date) -> int:
    tasks = db.scalars(
        select(DailyTask)
        .options(selectinload(DailyTask.report))
        .where(
            DailyTask.repeat_rule.in_(("daily", "weekly")),
            DailyTask.repeat_series_id.is_not(None),
            DailyTask.deleted_at.is_(None),
        )
    ).all()
    latest_by_series: dict[str, DailyTask] = {}
    for task in tasks:
        current = latest_by_series.get(task.repeat_series_id)
        if current is None or task.report.report_date > current.report.report_date:
            latest_by_series[task.repeat_series_id] = task

    known_task_ids = {task.id for task in tasks}
    created = 0
    for latest in latest_by_series.values():
        current_date = latest.report.report_date
        if current_date > through_date:
            continue
        candidate = next_repeat_date(current_date, latest.repeat_rule)
        while candidate < through_date:
            candidate = next_repeat_date(candidate, latest.repeat_rule)
        next_task = _create_next_repeat_occurrence(
            db, latest, current_date, occurrence_date=candidate
        )
        if next_task is None:
            continue
        if next_task.id not in known_task_ids:
            known_task_ids.add(next_task.id)
            created += 1
        if candidate == through_date:
            future_task = _create_next_repeat_occurrence(db, next_task, candidate)
            if future_task is not None and future_task.id not in known_task_ids:
                known_task_ids.add(future_task.id)
                created += 1
    db.commit()
    return created


class DailyService:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    def get_daily(self, report_date: date) -> DailyReport | None:
        return self.db.scalar(
            select(DailyReport)
            .options(
                selectinload(DailyReport.tasks).selectinload(DailyTask.collaborators),
                selectinload(DailyReport.problems),
            )
            .where(
                DailyReport.user_id == self.user.id,
                DailyReport.report_date == report_date,
                DailyReport.deleted_at.is_(None),
            )
        )

    def get_own_daily_out(self, report_date: date) -> DailyReportOut:
        report = self.get_daily(report_date)
        own_tasks = [] if report is None else [t for t in report.tasks if t.deleted_at is None]
        all_tasks = own_tasks + self.collaborator_tasks(report_date)
        tasks = [
            self.serialize_task(task)
            for task in sorted(all_tasks, key=lambda task: (task.task_time, task.id))
        ]
        if report is None:
            return DailyReportOut(
                id=None,
                user_id=self.user.id,
                report_date=report_date,
                status="draft",
                tasks=tasks,
                problems=[],
            )
        return DailyReportOut(
            id=report.id,
            user_id=report.user_id,
            report_date=report.report_date,
            status=report.status,
            tasks=tasks,
            problems=self._serialize_problems(report),
        )

    def get_own_range_out(self, start_date: date, end_date: date) -> list[DailyRangeDayOut]:
        reports = list(
            self.db.scalars(
                select(DailyReport)
                .options(selectinload(DailyReport.tasks).selectinload(DailyTask.collaborators))
                .where(
                    DailyReport.user_id == self.user.id,
                    DailyReport.report_date >= start_date,
                    DailyReport.report_date <= end_date,
                    DailyReport.deleted_at.is_(None),
                )
                .order_by(DailyReport.report_date)
            ).all()
        )
        tasks_by_date: dict[date, list[DailyTask]] = {
            report.report_date: [task for task in report.tasks if task.deleted_at is None]
            for report in reports
        }
        collaborator_rows = self.db.execute(
            select(DailyTask, DailyReport.report_date)
            .options(selectinload(DailyTask.collaborators))
            .join(DailyReport, DailyReport.id == DailyTask.report_id)
            .join(DailyTaskCollaborator, DailyTaskCollaborator.task_id == DailyTask.id)
            .where(
                DailyTaskCollaborator.user_id == self.user.id,
                DailyTaskCollaborator.deleted_at.is_(None),
                DailyTask.user_id != self.user.id,
                DailyTask.deleted_at.is_(None),
                DailyReport.report_date >= start_date,
                DailyReport.report_date <= end_date,
                DailyReport.deleted_at.is_(None),
            )
        ).all()
        for task, report_date in collaborator_rows:
            tasks_by_date.setdefault(report_date, []).append(task)

        days: list[DailyRangeDayOut] = []
        current = start_date
        while current <= end_date:
            tasks = sorted(
                tasks_by_date.get(current, []),
                key=lambda task: (task.task_time, task.id),
            )
            days.append(
                DailyRangeDayOut(
                    date=current,
                    tasks=[self.serialize_task(task) for task in tasks],
                )
            )
            current += timedelta(days=1)
        return days

    def get_followed_daily_out(self, target_user_id: int, report_date: date) -> DailyReportOut:
        report = self.db.scalar(
            select(DailyReport)
            .options(
                selectinload(DailyReport.tasks).selectinload(DailyTask.collaborators),
                selectinload(DailyReport.problems),
            )
            .where(
                DailyReport.user_id == target_user_id,
                DailyReport.report_date == report_date,
                DailyReport.deleted_at.is_(None),
            )
        )
        if report is None:
            return DailyReportOut(
                id=None,
                user_id=target_user_id,
                report_date=report_date,
                status="draft",
                tasks=[],
                problems=[],
            )
        tasks = [
            self.serialize_task(task, permission_override="follower")
            for task in sorted(
                [t for t in report.tasks if t.deleted_at is None and not t.is_private],
                key=lambda task: (task.task_time, task.id),
            )
        ]
        return DailyReportOut(
            id=report.id,
            user_id=report.user_id,
            report_date=report.report_date,
            status=report.status,
            tasks=tasks,
            problems=self._serialize_problems(report),
        )

    def collaborator_tasks(self, report_date: date) -> list[DailyTask]:
        return list(
            self.db.scalars(
                select(DailyTask)
                .options(selectinload(DailyTask.collaborators))
                .join(DailyReport, DailyReport.id == DailyTask.report_id)
                .join(DailyTaskCollaborator, DailyTaskCollaborator.task_id == DailyTask.id)
                .where(
                    DailyTaskCollaborator.user_id == self.user.id,
                    DailyTaskCollaborator.deleted_at.is_(None),
                    DailyTask.user_id != self.user.id,
                    DailyTask.deleted_at.is_(None),
                    DailyReport.report_date == report_date,
                    DailyReport.deleted_at.is_(None),
                )
            ).all()
        )

    def week_summary(self, anchor: date) -> list[dict]:
        days = week_dates(anchor)
        # The week-strip dot marks days that still have outstanding work: at
        # least one incomplete task. Completed-only days and problem-only days
        # do not show a dot.
        rows = self.db.execute(
            select(DailyReport.report_date, func.count(DailyTask.id))
            .outerjoin(
                DailyTask,
                (DailyTask.report_id == DailyReport.id)
                & (DailyTask.deleted_at.is_(None))
                & (DailyTask.is_done.is_(False)),
            )
            .where(
                DailyReport.user_id == self.user.id,
                DailyReport.report_date.in_(days),
                DailyReport.deleted_at.is_(None),
            )
            .group_by(DailyReport.report_date)
        ).all()
        content_dates = {row[0] for row in rows if row[1]}
        return [{"date": day, "has_content": day in content_dates} for day in days]

    def create_task(self, payload: DailyTaskCreate) -> DailyTask:
        # Dispatch: when a target points at someone else, the task is owned by that
        # assignee (lands in their report for the date). Ownership fully transfers —
        # the assignee marks it done directly (no accept/reject flow).
        # assigned_to_ids may hold multiple targets (a 人员组 expanded on the frontend);
        # each target gets their own task. Self is allowed as a dispatch target.
        targets = list(dict.fromkeys(payload.assigned_to_ids))
        self._validate_users(payload.collaborator_ids)
        if targets:
            self._validate_users(targets)

        # Owners to create tasks for: each dispatch target, or just self when none.
        owner_ids = targets or [self.user.id]
        first_task: DailyTask | None = None
        for owner_id in owner_ids:
            dispatched = bool(targets)
            report = self._get_or_create_report(owner_id, payload.date)
            task = DailyTask(
                report_id=report.id,
                user_id=owner_id,
                task_time=payload.task_time,
                content=payload.content.strip(),
                note=(payload.note.strip() or None) if payload.note else None,
                is_private=payload.is_private,
                repeat_rule=payload.repeat_rule,
                repeat_series_id=(
                    str(uuid4()) if payload.repeat_rule in {"daily", "weekly"} else None
                ),
                source="assigned" if dispatched else "manual",
                assigned_to=owner_id if dispatched else None,
                assigned_by=self.user.id if dispatched else None,
                sort_order=self._next_sort(DailyTask, report.id),
                created_by=self.user.id,
                updated_by=self.user.id,
            )
            self.db.add(task)
            self.db.flush()
            new_collaborator_ids = self._set_collaborators(task, payload.collaborator_ids)
            self.db.flush()
            self._notify_task_participants(
                task,
                payload.date,
                assigned=dispatched,
                collaborator_ids=new_collaborator_ids,
            )
            _create_next_repeat_occurrence(self.db, task, payload.date)
            if first_task is None:
                first_task = task
        if targets:
            self._ensure_dispatch_subscriptions(targets)
        self.db.commit()
        self.db.refresh(first_task)
        return first_task

    def update_task(self, task_id: int, payload: DailyTaskUpdate) -> DailyTask:
        task = self._get_owned_task(task_id)
        report_date = self.db.scalar(
            select(DailyReport.report_date).where(DailyReport.id == task.report_id)
        )
        future_tasks = self._future_repeat_tasks(task, report_date)
        if payload.task_time is not None:
            task.task_time = payload.task_time
            for future in future_tasks:
                future.task_time = payload.task_time
        if payload.content is not None:
            task.content = payload.content.strip()
            for future in future_tasks:
                future.content = task.content
        if "note" in payload.model_fields_set:
            task.note = (payload.note.strip() or None) if payload.note else None
            for future in future_tasks:
                future.note = task.note
        if payload.is_private is not None:
            task.is_private = payload.is_private
            for future in future_tasks:
                future.is_private = payload.is_private
        if payload.sort_order is not None:
            task.sort_order = payload.sort_order
        if payload.collaborator_ids is not None:
            self._validate_users(payload.collaborator_ids)
            added_collaborator_ids = self._set_collaborators(task, payload.collaborator_ids)
            self._notify_task_participants(
                task,
                report_date,
                assigned=False,
                collaborator_ids=added_collaborator_ids,
            )
            for future in future_tasks:
                if future.deleted_at is None:
                    self._set_collaborators(future, payload.collaborator_ids)
            self.db.flush()
        if payload.repeat_rule is not None:
            previous_rule = task.repeat_rule
            task.repeat_rule = payload.repeat_rule
            if payload.repeat_rule == "none":
                self._stop_repeat_series(task, report_date, delete_current=False)
            else:
                if not task.repeat_series_id:
                    task.repeat_series_id = str(uuid4())
                if previous_rule != payload.repeat_rule:
                    for future in future_tasks:
                        future.deleted_at = utcnow()
                        future.updated_by = self.user.id
                    self.db.flush()
                _create_next_repeat_occurrence(self.db, task, report_date)
        if payload.assigned_to_ids:
            targets = list(dict.fromkeys(payload.assigned_to_ids))
            self._validate_users(targets)
            self.db.flush()
            dispatched = self._dispatch_updated_task(task, report_date, targets)
            self.db.commit()
            self.db.refresh(dispatched)
            return dispatched
        task.updated_by = self.user.id
        self.db.commit()
        self.db.refresh(task)
        return task

    def _dispatch_updated_task(
        self,
        task: DailyTask,
        report_date: date,
        target_user_ids: list[int],
    ) -> DailyTask:
        collaborator_ids = list(
            self.db.scalars(
                select(DailyTaskCollaborator.user_id).where(
                    DailyTaskCollaborator.task_id == task.id,
                    DailyTaskCollaborator.deleted_at.is_(None),
                )
            ).all()
        )
        first_task: DailyTask | None = None
        for owner_id in target_user_ids:
            report = self._get_or_create_report(owner_id, report_date)
            dispatched = DailyTask(
                report_id=report.id,
                user_id=owner_id,
                task_time=task.task_time,
                content=task.content,
                note=task.note,
                is_private=task.is_private,
                repeat_rule=task.repeat_rule,
                repeat_series_id=(
                    str(uuid4()) if task.repeat_rule in {"daily", "weekly"} else None
                ),
                source="assigned",
                assigned_to=owner_id,
                assigned_by=self.user.id,
                sort_order=self._next_sort(DailyTask, report.id),
                created_by=self.user.id,
                updated_by=self.user.id,
            )
            self.db.add(dispatched)
            self.db.flush()
            added_collaborator_ids = self._set_collaborators(dispatched, collaborator_ids)
            self.db.flush()
            self._notify_task_participants(
                dispatched,
                report_date,
                assigned=True,
                collaborator_ids=added_collaborator_ids,
            )
            _create_next_repeat_occurrence(self.db, dispatched, report_date)
            if first_task is None:
                first_task = dispatched

        self._ensure_dispatch_subscriptions(target_user_ids)
        self._stop_repeat_series(task, report_date, delete_current=True)
        task.deleted_at = utcnow()
        task.updated_by = self.user.id
        if first_task is None:
            raise RuntimeError("dispatch requires at least one target")
        return first_task

    def set_task_done(self, task_id: int, payload: DailyTaskDoneIn) -> DailyTask:
        task = self._get_task_for_done(task_id)
        task.is_done = payload.is_done
        task.done_at = utcnow() if payload.is_done else None
        task.updated_by = self.user.id
        self.db.commit()
        self.db.refresh(task)
        return task

    def delete_task(self, task_id: int) -> None:
        task = self._get_owned_task(task_id)
        report_date = self.db.scalar(
            select(DailyReport.report_date).where(DailyReport.id == task.report_id)
        )
        self._stop_repeat_series(task, report_date, delete_current=True)
        task.deleted_at = utcnow()
        task.updated_by = self.user.id
        self.db.commit()

    def _stop_repeat_series(
        self, task: DailyTask, report_date: date | None, *, delete_current: bool
    ) -> None:
        series_id = task.repeat_series_id
        if not series_id or report_date is None:
            task.repeat_series_id = None
            return
        occurrences = self.db.execute(
            select(DailyTask, DailyReport.report_date)
            .join(DailyReport, DailyReport.id == DailyTask.report_id)
            .where(
                DailyTask.repeat_series_id == series_id,
                DailyTask.deleted_at.is_(None),
                DailyReport.deleted_at.is_(None),
            )
        ).all()
        stopped_at = utcnow()
        for occurrence, occurrence_date in occurrences:
            if occurrence_date > report_date or (
                delete_current and occurrence.id == task.id
            ):
                occurrence.deleted_at = stopped_at
                occurrence.updated_by = self.user.id
            else:
                occurrence.repeat_series_id = None

    def _future_repeat_tasks(
        self, task: DailyTask, report_date: date | None
    ) -> list[DailyTask]:
        if not task.repeat_series_id or report_date is None:
            return []
        return list(
            self.db.scalars(
                select(DailyTask)
                .join(DailyReport, DailyReport.id == DailyTask.report_id)
                .where(
                    DailyTask.repeat_series_id == task.repeat_series_id,
                    DailyReport.report_date > report_date,
                    DailyTask.deleted_at.is_(None),
                    DailyReport.deleted_at.is_(None),
                )
                .order_by(DailyReport.report_date)
            ).all()
        )

    def create_problem(self, payload: ProblemSolutionCreate) -> ProblemSolution:
        report = self._get_or_create_report(self.user.id, payload.date)
        solution_html = sanitize_html(payload.solution_html)
        problem = ProblemSolution(
            report_id=report.id,
            user_id=self.user.id,
            problem_text=payload.problem_text.strip(),
            solution_html=solution_html,
            solution_json=payload.solution_json,
            search_text=self._search_text(payload.problem_text, solution_html),
            sort_order=self._next_sort(ProblemSolution, report.id),
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        self.db.add(problem)
        self.db.commit()
        self.db.refresh(problem)
        return problem

    def update_problem(self, problem_id: int, payload: ProblemSolutionUpdate) -> ProblemSolution:
        problem = self._get_problem(problem_id)
        if payload.problem_text is not None:
            problem.problem_text = payload.problem_text.strip()
        if payload.solution_html is not None:
            problem.solution_html = sanitize_html(payload.solution_html)
        if payload.solution_json is not None:
            problem.solution_json = payload.solution_json
        if payload.sort_order is not None:
            problem.sort_order = payload.sort_order
        problem.search_text = self._search_text(problem.problem_text, problem.solution_html or "")
        problem.updated_by = self.user.id
        self.db.commit()
        self.db.refresh(problem)
        return problem

    def delete_problem(self, problem_id: int) -> None:
        problem = self._get_problem(problem_id)
        problem.deleted_at = utcnow()
        problem.updated_by = self.user.id
        self.db.commit()

    def _get_or_create_report(self, owner_id: int, report_date: date) -> DailyReport:
        report = self.db.scalar(
            select(DailyReport).where(
                DailyReport.user_id == owner_id,
                DailyReport.report_date == report_date,
                DailyReport.deleted_at.is_(None),
            )
        )
        if report is not None:
            return report
        report = DailyReport(
            user_id=owner_id,
            report_date=report_date,
            status="draft",
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        self.db.add(report)
        self.db.flush()
        return report

    def _validate_users(self, user_ids: list[int]) -> None:
        ids = set(user_ids)
        if not ids:
            return
        found = set(
            self.db.scalars(
                select(User.id).where(
                    User.id.in_(ids),
                    User.status == "active",
                    User.deleted_at.is_(None),
                )
            ).all()
        )
        missing = ids - found
        if missing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown user(s)")

    def _set_collaborators(self, task: DailyTask, collaborator_ids: list[int]) -> set[int]:
        wanted = {uid for uid in collaborator_ids if uid != task.user_id}
        existing = self.db.scalars(
            select(DailyTaskCollaborator).where(
                DailyTaskCollaborator.task_id == task.id,
            )
        ).all()
        by_user = {row.user_id: row for row in existing}
        active = {row.user_id for row in existing if row.deleted_at is None}
        for uid, row in by_user.items():
            if uid not in wanted:
                row.deleted_at = utcnow()
                row.updated_by = self.user.id
        for uid in wanted:
            row = by_user.get(uid)
            if row is not None:
                row.deleted_at = None
                row.updated_by = self.user.id
                continue
            self.db.add(
                DailyTaskCollaborator(
                    task_id=task.id,
                    user_id=uid,
                    created_by=self.user.id,
                    updated_by=self.user.id,
                )
            )
        return wanted - active

    def _notify_task_participants(
        self,
        task: DailyTask,
        report_date: date,
        *,
        assigned: bool,
        collaborator_ids: set[int],
    ) -> None:
        service = NotificationService(self.db, self.user)
        if assigned and task.user_id != self.user.id:
            recipient = self.db.get(User, task.user_id)
            if recipient is not None:
                service.notify(
                    recipient=recipient,
                    actor_id=self.user.id,
                    notification_type="daily.assigned",
                    title="收到新的日报任务",
                    body=f"{self.user.name} 向你派发了任务：{task.content}",
                    action_url=f"/daily?date={report_date.isoformat()}",
                    entity_type="daily_task",
                    entity_id=task.id,
                    dedupe_key=f"daily.assigned:{task.id}:{task.user_id}",
                )
        for collaborator_id in collaborator_ids - {task.user_id, self.user.id}:
            recipient = self.db.get(User, collaborator_id)
            if recipient is not None:
                service.notify(
                    recipient=recipient,
                    actor_id=self.user.id,
                    notification_type="daily.collaborator_added",
                    title="你已成为日报任务协作者",
                    body=f"你已成为“{task.content}”的协作者。",
                    action_url=f"/daily?date={report_date.isoformat()}",
                    entity_type="daily_task",
                    entity_id=task.id,
                    dedupe_key=f"daily.collaborator_added:{task.id}:{collaborator_id}",
                )

    def _ensure_dispatch_subscriptions(self, target_user_ids: list[int]) -> None:
        target_ids = [uid for uid in dict.fromkeys(target_user_ids) if uid != self.user.id]
        if not target_ids:
            return
        existing = self.db.scalars(
            select(Subscription).where(
                Subscription.subscriber_id == self.user.id,
                Subscription.target_user_id.in_(target_ids),
            )
        ).all()
        by_target = {row.target_user_id: row for row in existing}
        now = utcnow()
        for target_id in target_ids:
            row = by_target.get(target_id)
            if row is None:
                self.db.add(
                    Subscription(
                        subscriber_id=self.user.id,
                        target_user_id=target_id,
                        daily_enabled=True,
                        okr_enabled=False,
                        created_by=self.user.id,
                        updated_by=self.user.id,
                    )
                )
                continue
            row.daily_enabled = True
            row.deleted_at = None
            row.updated_by = self.user.id
            row.updated_at = now

    def _get_owned_task(self, task_id: int) -> DailyTask:
        task = self.db.scalar(
            select(DailyTask).where(
                DailyTask.id == task_id,
                DailyTask.user_id == self.user.id,
                DailyTask.deleted_at.is_(None),
            )
        )
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task

    def _get_task_for_done(self, task_id: int) -> DailyTask:
        task = self.db.scalar(
            select(DailyTask)
            .options(selectinload(DailyTask.collaborators))
            .where(DailyTask.id == task_id, DailyTask.deleted_at.is_(None))
        )
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        if task.user_id == self.user.id:
            return task
        is_collaborator = any(c.user_id == self.user.id and c.deleted_at is None for c in task.collaborators)
        if is_collaborator:
            return task
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

    def _get_problem(self, problem_id: int) -> ProblemSolution:
        problem = self.db.scalar(
            select(ProblemSolution).where(
                ProblemSolution.id == problem_id,
                ProblemSolution.user_id == self.user.id,
                ProblemSolution.deleted_at.is_(None),
            )
        )
        if problem is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Problem not found")
        return problem

    def serialize_task(self, task: DailyTask, permission_override: str | None = None) -> DailyTaskOut:
        collab_ids = [c.user_id for c in task.collaborators if c.deleted_at is None]
        collaborators: list[UserBrief] = []
        if collab_ids:
            users = self.db.scalars(
                select(User).where(User.id.in_(collab_ids), User.deleted_at.is_(None))
            ).all()
            collaborators = [UserBrief.model_validate(u) for u in users]
        permission = permission_override or self._task_permission(task, collab_ids)
        is_follower = permission == "follower"
        return DailyTaskOut(
            id=task.id,
            report_id=task.report_id,
            user_id=task.user_id,
            task_time=task.task_time,
            content=task.content,
            note=task.note,
            is_private=task.is_private,
            is_done=task.is_done,
            done_at=task.done_at,
            repeat_rule=task.repeat_rule,
            source=task.source,
            assigned_to=task.assigned_to,
            assigned_by=task.assigned_by,
            sort_order=task.sort_order,
            collaborators=collaborators,
            permission=permission,
            can_edit=False if is_follower else task.user_id == self.user.id,
            can_delete=False if is_follower else task.user_id == self.user.id,
            can_toggle_done=False if is_follower else task.user_id == self.user.id or self.user.id in collab_ids,
            can_manage_members=False if is_follower else task.user_id == self.user.id,
        )

    def _task_permission(self, task: DailyTask, collab_ids: list[int]) -> str:
        if task.user_id == self.user.id:
            return "owner"
        if self.user.id in collab_ids:
            return "collaborator"
        return "follower"

    def _next_sort(self, model: type[DailyTask] | type[ProblemSolution], report_id: int) -> int:
        value = self.db.scalar(
            select(func.max(model.sort_order)).where(model.report_id == report_id, model.deleted_at.is_(None))
        )
        return int(value or 0) + 1

    def _serialize_problems(self, report: DailyReport) -> list[ProblemSolution]:
        return [
            item
            for item in sorted(report.problems, key=lambda problem: problem.sort_order)
            if item.deleted_at is None
        ]

    def _search_text(self, problem_text: str, solution_html: str) -> str:
        return f"{problem_text.strip()} {extract_text(solution_html)}".strip()
