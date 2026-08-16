from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.security import utcnow
from app.models.traffic import (
    TrafficMetric,
    TrafficMetricAssignment,
    TrafficMetricMember,
    TrafficMetricValue,
)
from app.models.user import User
from app.schemas.traffic import TrafficMetricCreate, TrafficMetricUpdate, TrafficMetricValueUpdate
from app.utils.dates import WeekColumn, last_completed_week_start, recent_weeks, week_start_for
from app.utils.time import local_today

DEFAULT_WEEK_COUNT = 5


class TrafficService:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    def resolve_window(self, anchor: date | None, count: int) -> list[WeekColumn]:
        if count < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="count must be >= 1",
            )
        end_week_start = week_start_for(anchor or local_today())
        return recent_weeks(end_week_start, count)

    def list_metrics(self, anchor: date | None, count: int = DEFAULT_WEEK_COUNT) -> list[dict]:
        columns = self.resolve_window(anchor, count)
        assigned_metric_ids = select(TrafficMetricAssignment.metric_id).where(
            TrafficMetricAssignment.assignee_id == self.user.id,
            TrafficMetricAssignment.deleted_at.is_(None),
        )
        viewed_metric_ids = select(TrafficMetricMember.metric_id).where(
            TrafficMetricMember.user_id == self.user.id,
            TrafficMetricMember.role == "viewer",
            TrafficMetricMember.deleted_at.is_(None),
        )
        metrics = self.db.scalars(
            self._metric_select().where(
                TrafficMetric.deleted_at.is_(None),
                (TrafficMetric.owner_id == self.user.id)
                | (TrafficMetric.id.in_(assigned_metric_ids))
                | (TrafficMetric.id.in_(viewed_metric_ids)),
            )
            .order_by(TrafficMetric.sort_order, TrafficMetric.id)
        ).all()
        rows: list[dict] = []
        for metric in metrics:
            rows.extend(self._serialize_metric_rows(metric, columns))
        return rows

    def create_metric(self, payload: TrafficMetricCreate) -> list[dict]:
        self._validate_goal(payload.direction, payload.weekly_target)
        metric = TrafficMetric(
            owner_id=self.user.id,
            name=payload.name.strip(),
            unit=payload.unit.strip() if payload.unit else None,
            direction=payload.direction,
            weekly_target=payload.weekly_target,
            north_star_target=payload.north_star_target,
            sort_order=self._next_sort(),
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        self.db.add(metric)
        self.db.flush()
        assignee_ids = self._sync_assignments(metric, payload.editor_ids)
        self._set_viewers(metric, payload.viewer_ids, assignee_ids)
        self.db.commit()
        metric = self._get_metric(metric.id)
        return self._serialize_metric_rows(metric, self.resolve_window(None, DEFAULT_WEEK_COUNT))

    def update_metric(self, metric_id: int, payload: TrafficMetricUpdate) -> list[dict]:
        metric = self._get_metric(metric_id, require_owner=True)
        supplied = payload.model_fields_set
        for field in (
            "name",
            "unit",
            "direction",
            "weekly_target",
            "north_star_target",
            "sort_order",
        ):
            if field not in supplied:
                continue
            value = getattr(payload, field)
            if field in {"name", "direction", "sort_order"} and value is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field} cannot be null",
                )
            setattr(metric, field, value.strip() if isinstance(value, str) else value)
        self._validate_goal(metric.direction, metric.weekly_target)

        assignee_ids = (
            self._sync_assignments(metric, payload.editor_ids)
            if payload.editor_ids is not None
            else self._active_assignee_ids(metric)
        )
        if payload.viewer_ids is not None or payload.editor_ids is not None:
            viewer_ids = (
                payload.viewer_ids
                if payload.viewer_ids is not None
                else self._active_viewer_ids(metric)
            )
            self._set_viewers(metric, viewer_ids, assignee_ids)

        metric.updated_by = self.user.id
        for row in metric.values:
            if row.deleted_at is None:
                row.status = self._week_status(metric, row.value)
                row.updated_by = self.user.id
        self.db.commit()
        metric = self._get_metric(metric_id)
        return self._serialize_metric_rows(metric, self.resolve_window(None, DEFAULT_WEEK_COUNT))

    def delete_metric(self, metric_id: int) -> None:
        metric = self._get_metric(metric_id, require_owner=True)
        deleted_at = utcnow()
        metric.deleted_at = deleted_at
        metric.updated_by = self.user.id
        for assignment in metric.assignments:
            if assignment.deleted_at is None:
                assignment.deleted_at = deleted_at
                assignment.updated_by = self.user.id
        for member in metric.members:
            if member.deleted_at is None:
                member.deleted_at = deleted_at
                member.updated_by = self.user.id
        for value in metric.values:
            if value.deleted_at is None:
                value.deleted_at = deleted_at
                value.updated_by = self.user.id
        self.db.commit()

    def upsert_value(
        self,
        assignment_id: int,
        week_start: date,
        payload: TrafficMetricValueUpdate,
    ) -> dict:
        assignment, metric = self._get_assignment(assignment_id, require_assignee=True)
        monday = week_start_for(week_start)
        if monday < assignment.effective_from:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot fill a week before the assignment started",
            )
        if monday > week_start_for(local_today()):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot fill a future week",
            )
        sunday = monday + timedelta(days=6)

        value_row = self.db.scalar(
            select(TrafficMetricValue).where(
                TrafficMetricValue.assignment_id == assignment.id,
                TrafficMetricValue.week_start == monday,
                TrafficMetricValue.deleted_at.is_(None),
            )
        )
        if value_row is None:
            value_row = TrafficMetricValue(
                metric_id=metric.id,
                assignment_id=assignment.id,
                week_start=monday,
                week_end=sunday,
                created_by=self.user.id,
            )
            self.db.add(value_row)

        value_row.value = payload.value
        value_row.note = payload.note
        value_row.week_end = sunday
        value_row.updated_by = self.user.id
        value_row.status = self._week_status(metric, payload.value)
        self.db.commit()

        metric = self._get_metric(metric.id)
        assignment = next(row for row in metric.assignments if row.id == assignment_id)
        return self._serialize_metric(metric, assignment, self.resolve_window(monday, DEFAULT_WEEK_COUNT))

    def _metric_select(self):
        return select(TrafficMetric).options(
            selectinload(TrafficMetric.values),
            selectinload(TrafficMetric.members).selectinload(TrafficMetricMember.user),
            selectinload(TrafficMetric.assignments).selectinload(
                TrafficMetricAssignment.assignee
            ),
        )

    def _get_metric(self, metric_id: int, require_owner: bool = False) -> TrafficMetric:
        metric = self.db.scalar(
            self._metric_select().where(
                TrafficMetric.id == metric_id,
                TrafficMetric.deleted_at.is_(None),
            )
        )
        if metric is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
        if require_owner and metric.owner_id != self.user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")
        if not require_owner and not self._can_view_metric(metric):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
        return metric

    def _get_assignment(
        self,
        assignment_id: int,
        require_assignee: bool = False,
    ) -> tuple[TrafficMetricAssignment, TrafficMetric]:
        assignment = self.db.scalar(
            select(TrafficMetricAssignment).where(
                TrafficMetricAssignment.id == assignment_id,
                TrafficMetricAssignment.deleted_at.is_(None),
            )
        )
        if assignment is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Metric assignment not found",
            )
        metric = self._get_metric(assignment.metric_id)
        if require_assignee and assignment.assignee_id != self.user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Assignee only",
            )
        return assignment, metric

    def _can_view_metric(self, metric: TrafficMetric) -> bool:
        if metric.owner_id == self.user.id:
            return True
        if any(
            assignment.assignee_id == self.user.id and assignment.deleted_at is None
            for assignment in metric.assignments
        ):
            return True
        return self._is_viewer(metric)

    def _is_viewer(self, metric: TrafficMetric) -> bool:
        return any(
            member.user_id == self.user.id
            and member.role == "viewer"
            and member.deleted_at is None
            for member in metric.members
        )

    def _active_assignee_ids(self, metric: TrafficMetric) -> list[int]:
        return [
            assignment.assignee_id
            for assignment in metric.assignments
            if assignment.deleted_at is None
        ]

    def _active_viewer_ids(self, metric: TrafficMetric) -> list[int]:
        return [
            member.user_id
            for member in metric.members
            if member.role == "viewer" and member.deleted_at is None
        ]

    def _validate_users(self, ids: set[int]) -> None:
        ids = {user_id for user_id in ids if user_id != self.user.id}
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
        if ids - found:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown user(s)")

    def _sync_assignments(self, metric: TrafficMetric, assignee_ids: list[int]) -> list[int]:
        wanted = list(dict.fromkeys(assignee_ids))
        self._validate_users(set(wanted))
        wanted_set = set(wanted)
        existing = {assignment.assignee_id: assignment for assignment in metric.assignments}
        effective_from = last_completed_week_start(local_today())

        for user_id, assignment in existing.items():
            if user_id not in wanted_set:
                if assignment.deleted_at is None:
                    assignment.deleted_at = utcnow()
                    assignment.updated_by = self.user.id
                continue
            if assignment.deleted_at is not None:
                assignment.effective_from = effective_from
            assignment.deleted_at = None
            assignment.assigned_by_id = self.user.id
            assignment.updated_by = self.user.id

        for user_id in wanted:
            if user_id not in existing:
                self.db.add(
                    TrafficMetricAssignment(
                        metric_id=metric.id,
                        assignee_id=user_id,
                        assigned_by_id=self.user.id,
                        effective_from=effective_from,
                        created_by=self.user.id,
                        updated_by=self.user.id,
                    )
                )
        self.db.flush()
        return wanted

    def _set_viewers(
        self,
        metric: TrafficMetric,
        viewer_ids: list[int],
        assignee_ids: list[int],
    ) -> None:
        assignee_set = set(assignee_ids)
        wanted = {
            user_id
            for user_id in viewer_ids
            if user_id != metric.owner_id and user_id not in assignee_set
        }
        self._validate_users(wanted)
        existing = {member.user_id: member for member in metric.members}
        for user_id, member in existing.items():
            if user_id not in wanted:
                if member.deleted_at is None:
                    member.deleted_at = utcnow()
                    member.updated_by = self.user.id
                continue
            member.deleted_at = None
            member.role = "viewer"
            member.updated_by = self.user.id
        for user_id in wanted:
            if user_id not in existing:
                self.db.add(
                    TrafficMetricMember(
                        metric_id=metric.id,
                        user_id=user_id,
                        role="viewer",
                        created_by=self.user.id,
                        updated_by=self.user.id,
                    )
                )

    def _next_sort(self) -> int:
        value = self.db.scalar(
            select(func.max(TrafficMetric.sort_order)).where(
                TrafficMetric.owner_id == self.user.id,
                TrafficMetric.deleted_at.is_(None),
            )
        )
        return int(value or 0) + 1

    def _validate_goal(self, direction: str, weekly_target: Decimal | None) -> None:
        if direction not in {"increase", "decrease"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="direction must be increase/decrease",
            )
        if weekly_target is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="weekly_target is required",
            )

    def _week_status(self, metric: TrafficMetric, value: Decimal | None) -> str:
        if value is None or metric.weekly_target is None:
            return "missed"
        if metric.direction == "increase":
            return "on_target" if value >= metric.weekly_target else "missed"
        if metric.direction == "decrease":
            return "on_target" if value <= metric.weekly_target else "missed"
        return "missed"

    def _serialize_metric_rows(
        self,
        metric: TrafficMetric,
        columns: list[WeekColumn],
    ) -> list[dict]:
        active_assignments = sorted(
            (
                assignment
                for assignment in metric.assignments
                if assignment.deleted_at is None
            ),
            key=lambda assignment: assignment.id,
        )
        can_view_all = metric.owner_id == self.user.id or self._is_viewer(metric)
        if can_view_all:
            visible_assignments = active_assignments
        else:
            visible_assignments = [
                assignment
                for assignment in active_assignments
                if assignment.assignee_id == self.user.id
            ]
        if not visible_assignments and metric.owner_id == self.user.id:
            return [self._serialize_metric(metric, None, columns)]
        return [
            self._serialize_metric(metric, assignment, columns)
            for assignment in visible_assignments
        ]

    def _serialize_assignee(self, assignment: TrafficMetricAssignment) -> dict:
        return {
            "assignment_id": assignment.id,
            "user_id": assignment.assignee.id,
            "name": assignment.assignee.name,
            "avatar_url": assignment.assignee.avatar_url,
            "effective_from": assignment.effective_from,
        }

    def _serialize_metric(
        self,
        metric: TrafficMetric,
        assignment: TrafficMetricAssignment | None,
        columns: list[WeekColumn],
    ) -> dict:
        window_starts = {column.week_start for column in columns}
        personal_values = [
            value
            for value in metric.values
            if assignment is not None
            and value.assignment_id == assignment.id
            and value.deleted_at is None
            and value.week_start in window_starts
        ]
        value_by_week = {value.week_start: value for value in personal_values}
        serialized_values = [
            {
                "id": value.id,
                "metric_id": value.metric_id,
                "assignment_id": value.assignment_id,
                "week_start": value.week_start,
                "week_end": value.week_end,
                "value": value.value,
                "status": value.status,
                "note": value.note,
            }
            for value in sorted(value_by_week.values(), key=lambda item: item.week_start)
        ]

        filled = [value.value for value in personal_values if value.value is not None]
        recent_avg = (
            (sum(filled, Decimal("0")) / Decimal(len(filled))).quantize(Decimal("0.0001"))
            if filled
            else None
        )
        newest_start = columns[-1].week_start if columns else None
        newest_value = next(
            (value for value in personal_values if value.week_start == newest_start),
            None,
        )
        can_edit_values = (
            assignment is not None and assignment.assignee_id == self.user.id
        )
        is_pending = (
            can_edit_values
            and newest_start is not None
            and newest_start >= assignment.effective_from
            and (newest_value is None or newest_value.value is None)
        )
        active_assignments = [
            row for row in metric.assignments if row.deleted_at is None
        ]
        can_view_all = metric.owner_id == self.user.id or self._is_viewer(metric)
        visible_assignees = (
            active_assignments
            if can_view_all
            else [row for row in active_assignments if row.assignee_id == self.user.id]
        )
        members = [
            {
                "user_id": member.user.id,
                "name": member.user.name,
                "avatar_url": member.user.avatar_url,
                "role": "viewer",
            }
            for member in metric.members
            if member.deleted_at is None and member.role == "viewer"
        ]
        if metric.owner_id == self.user.id:
            role = "owner"
        elif assignment is not None and assignment.assignee_id == self.user.id:
            role = "assignee"
        else:
            role = "viewer"
        return {
            "id": metric.id,
            "assignment_id": assignment.id if assignment else None,
            "owner_id": metric.owner_id,
            "assignee": self._serialize_assignee(assignment) if assignment else None,
            "name": metric.name,
            "unit": metric.unit,
            "direction": metric.direction,
            "weekly_target": metric.weekly_target,
            "north_star_target": metric.north_star_target,
            "sort_order": metric.sort_order,
            "values": serialized_values,
            "recent_avg": recent_avg,
            "status": self._window_status(personal_values),
            "members": members,
            "assignees": [self._serialize_assignee(row) for row in visible_assignees],
            "my_role": role,
            "can_edit_values": can_edit_values,
            "can_edit_meta": metric.owner_id == self.user.id,
            "can_manage_members": metric.owner_id == self.user.id,
            "can_delete": metric.owner_id == self.user.id,
            "is_pending": is_pending,
        }

    def _window_status(self, values: list[TrafficMetricValue]) -> str:
        filled = [value for value in values if value.value is not None]
        if not filled:
            return "empty"
        if any(value.status == "missed" for value in filled):
            return "missed"
        return "on_target"
