from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.traffic import TrafficMetric, TrafficMetricMember, TrafficMetricValue
from app.models.user import User
from app.schemas.traffic import TrafficMetricCreate, TrafficMetricUpdate, TrafficMetricValueUpdate
from app.utils.dates import (
    WeekColumn,
    last_completed_week_start,
    recent_weeks,
    week_start_for,
)
from app.utils.time import local_today
from app.core.security import utcnow

DEFAULT_WEEK_COUNT = 5


class TrafficService:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    def resolve_window(self, anchor: date | None, count: int) -> list[WeekColumn]:
        """Rolling window of ``count`` weeks ending at ``anchor``'s week.

        ``anchor`` defaults to the most recently completed week (the newest
        fillable week). Callers page backwards by passing an earlier anchor.
        """
        if count < 1:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="count must be >= 1"
            )
        end_week_start = week_start_for(anchor) if anchor else last_completed_week_start(local_today())
        return recent_weeks(end_week_start, count)

    def list_metrics(self, anchor: date | None, count: int = DEFAULT_WEEK_COUNT) -> list[dict]:
        columns = self.resolve_window(anchor, count)
        member_metric_ids = select(TrafficMetricMember.metric_id).where(
            TrafficMetricMember.user_id == self.user.id,
            TrafficMetricMember.deleted_at.is_(None),
        )
        metrics = self.db.scalars(
            select(TrafficMetric)
            .options(selectinload(TrafficMetric.values), selectinload(TrafficMetric.members))
            .where(
                TrafficMetric.deleted_at.is_(None),
                (TrafficMetric.owner_id == self.user.id) | (TrafficMetric.id.in_(member_metric_ids)),
            )
            .order_by(TrafficMetric.sort_order, TrafficMetric.id)
        ).all()
        return [self._serialize_metric(metric, columns) for metric in metrics]

    def create_metric(self, payload: TrafficMetricCreate) -> dict:
        self._validate_goal(payload.direction, payload.weekly_target)
        metric = TrafficMetric(
            owner_id=self.user.id,
            name=payload.name.strip(),
            unit=payload.unit,
            direction=payload.direction,
            weekly_target=payload.weekly_target,
            north_star_target=payload.north_star_target,
            sort_order=self._next_sort(),
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        self.db.add(metric)
        self.db.flush()
        self._set_members(metric, payload.editor_ids, payload.viewer_ids)
        self.db.commit()
        metric = self._get_metric(metric.id)
        return self._serialize_metric(metric, self.resolve_window(None, DEFAULT_WEEK_COUNT))

    def update_metric(self, metric_id: int, payload: TrafficMetricUpdate) -> dict:
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
        if payload.editor_ids is not None or payload.viewer_ids is not None:
            editors = payload.editor_ids if payload.editor_ids is not None else self._member_ids(metric, "editor")
            viewers = payload.viewer_ids if payload.viewer_ids is not None else self._member_ids(metric, "viewer")
            self._set_members(metric, editors, viewers)
        metric.updated_by = self.user.id
        # Recompute stored statuses since the goal may have changed.
        for row in metric.values:
            if row.deleted_at is None:
                row.status = self._week_status(metric, row.value)
        self.db.commit()
        metric = self._get_metric(metric_id)
        return self._serialize_metric(metric, self.resolve_window(None, DEFAULT_WEEK_COUNT))

    def delete_metric(self, metric_id: int) -> None:
        metric = self._get_metric(metric_id, require_owner=True)
        metric.deleted_at = utcnow()
        metric.updated_by = self.user.id
        self.db.commit()

    def upsert_value(self, metric_id: int, week_start: date, payload: TrafficMetricValueUpdate) -> dict:
        metric = self._get_metric(metric_id, require_value_editor=True)
        monday = week_start_for(week_start)
        if monday > last_completed_week_start(local_today()):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cannot fill a week that has not finished yet",
            )
        sunday = monday + timedelta(days=6)

        value_row = self.db.scalar(
            select(TrafficMetricValue).where(
                TrafficMetricValue.metric_id == metric.id,
                TrafficMetricValue.week_start == monday,
                TrafficMetricValue.deleted_at.is_(None),
            )
        )
        if value_row is None:
            value_row = TrafficMetricValue(
                metric_id=metric.id,
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
        metric = self._get_metric(metric_id)
        return self._serialize_metric(metric, self.resolve_window(monday, DEFAULT_WEEK_COUNT))

    # ---- permissions & members -------------------------------------------------

    def _get_metric(
        self,
        metric_id: int,
        require_owner: bool = False,
        require_value_editor: bool = False,
    ) -> TrafficMetric:
        metric = self.db.scalar(
            select(TrafficMetric)
            .options(selectinload(TrafficMetric.values), selectinload(TrafficMetric.members))
            .where(TrafficMetric.id == metric_id, TrafficMetric.deleted_at.is_(None))
        )
        if metric is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
        role = self._role_for(metric)
        if role is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Metric not found")
        if require_owner and role != "owner":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner only")
        if require_value_editor and not self._can_edit_values(metric, role):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Value editor only")
        return metric

    def _role_for(self, metric: TrafficMetric) -> str | None:
        if metric.owner_id == self.user.id:
            return "owner"
        member = next(
            (m for m in metric.members if m.user_id == self.user.id and m.deleted_at is None),
            None,
        )
        if member is None:
            return None
        return member.role if member.role in {"editor", "viewer"} else None

    def _member_ids(self, metric: TrafficMetric, role: str) -> list[int]:
        return [m.user_id for m in metric.members if m.deleted_at is None and m.role == role]

    def _can_edit_values(self, metric: TrafficMetric, role: str) -> bool:
        if role == "editor":
            return True
        if role != "owner":
            return False
        return any(
            member.user_id == metric.owner_id
            and member.role == "editor"
            and member.deleted_at is None
            for member in metric.members
        )

    def _validate_users(self, ids: set[int]) -> None:
        ids = {uid for uid in ids if uid != self.user.id}
        if not ids:
            return
        found = set(
            self.db.scalars(
                select(User.id).where(
                    User.id.in_(ids), User.status == "active", User.deleted_at.is_(None)
                )
            ).all()
        )
        if ids - found:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown user(s)")

    def _set_members(
        self,
        metric: TrafficMetric,
        editor_ids: list[int],
        viewer_ids: list[int],
    ) -> None:
        # editor > viewer. The owner needs an explicit editor row to fill values.
        wanted: dict[int, str] = {}
        for uid in viewer_ids:
            if uid != metric.owner_id:
                wanted[uid] = "viewer"
        for uid in editor_ids:
            wanted[uid] = "editor"
        self._validate_users(set(wanted))
        existing = {m.user_id: m for m in metric.members}
        for uid, row in existing.items():
            if uid not in wanted:
                if row.deleted_at is None:
                    row.deleted_at = utcnow()
                    row.updated_by = self.user.id
            else:
                row.deleted_at = None
                row.role = wanted[uid]
                row.updated_by = self.user.id
        for uid, role in wanted.items():
            if uid not in existing:
                self.db.add(
                    TrafficMetricMember(
                        metric_id=metric.id,
                        user_id=uid,
                        role=role,
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

    # ---- goal / status ---------------------------------------------------------

    def _validate_goal(
        self,
        direction: str,
        weekly_target: Decimal | None,
    ) -> None:
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
        """Green (on_target) if the week's value meets the goal, else red (missed)."""
        if value is None:
            return "missed"
        target = metric.weekly_target
        if target is None:
            return "missed"
        if metric.direction == "increase":
            return "on_target" if value >= target else "missed"
        if metric.direction == "decrease":
            return "on_target" if value <= target else "missed"
        return "missed"

    # ---- serialization ---------------------------------------------------------

    def _serialize_metric(self, metric: TrafficMetric, columns: list[WeekColumn]) -> dict:
        window_starts = {c.week_start for c in columns}
        window_values = sorted(
            [
                v
                for v in metric.values
                if v.deleted_at is None and v.week_start in window_starts
            ],
            key=lambda v: v.week_start,
        )
        filled = [v.value for v in window_values if v.value is not None]
        recent_avg = (
            (sum(filled, Decimal("0")) / Decimal(len(filled))).quantize(Decimal("0.0001"))
            if filled
            else None
        )
        role = self._role_for(metric) or "viewer"

        newest_start = columns[-1].week_start if columns else None
        newest_value = next(
            (v for v in window_values if v.week_start == newest_start), None
        )
        can_edit_values = self._can_edit_values(metric, role)
        is_pending = (
            can_edit_values
            and newest_start is not None
            and (newest_value is None or newest_value.value is None)
        )
        members = [
            {
                "user_id": m.user.id,
                "name": m.user.name,
                "avatar_url": m.user.avatar_url,
                "role": m.role,
            }
            for m in metric.members
            if m.deleted_at is None and m.role in {"editor", "viewer"}
        ]
        return {
            "id": metric.id,
            "owner_id": metric.owner_id,
            "name": metric.name,
            "unit": metric.unit,
            "direction": metric.direction,
            "weekly_target": metric.weekly_target,
            "north_star_target": metric.north_star_target,
            "sort_order": metric.sort_order,
            "values": window_values,
            "recent_avg": recent_avg,
            "status": self._window_status(window_values, columns),
            "members": members,
            "my_role": role,
            "can_edit_values": can_edit_values,
            "can_edit_meta": role == "owner",
            "can_manage_members": role == "owner",
            "can_delete": role == "owner",
            "is_pending": is_pending,
        }

    def _window_status(self, values: list[TrafficMetricValue], columns: list[WeekColumn]) -> str:
        """Rollup for the window: red if any filled week missed, green if all
        filled weeks are on target, grey (empty) when nothing filled."""
        filled = [v for v in values if v.value is not None]
        if not filled:
            return "empty"
        if any(v.status == "missed" for v in filled):
            return "missed"
        return "on_target"
