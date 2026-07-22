from __future__ import annotations

import secrets
from datetime import date, time, timedelta
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import case, distinct, func, or_, select, true
from sqlalchemy.orm import Session, aliased

from app.core.security import utcnow
from app.models.daily import DailyReport, DailyTask, ProblemSolution
from app.models.org import Department
from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.people import (
    PersonAiScoreOut,
    PersonCalendarDayOut,
    PersonMonthlyDailyOut,
    PersonProfileOut,
    PersonSignatureUpdate,
    PersonSocialOut,
    PersonSubscriptionOut,
    PersonUserOut,
)
from app.utils.dates import month_bounds
from app.utils.image_upload import delete_managed_upload, validate_raster_image
from app.utils.time import local_now, local_today

AVATAR_UPLOAD_DIR = Path(__file__).resolve().parents[2] / "storage" / "uploads" / "avatars"
MAX_AVATAR_BYTES = 2 * 1024 * 1024


class PeopleService:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    def get_profile(self, target_user_id: int, month: str) -> PersonProfileOut:
        target = self._get_active_user(target_user_id)
        user_out = PersonUserOut.model_validate(target)
        user_out.department_name = self._department_name(target.department_id)
        return PersonProfileOut(
            user=user_out,
            is_self=target.id == self.user.id,
            subscription=self._subscription_state(target.id),
            social=self._social_counts(target.id),
            daily_score=self._latest_daily_score(target.id),
            okr_review=self._latest_okr_review(target.id),
            daily_calendar=self._daily_calendar(target.id, month),
        )

    def subscribe_person(
        self,
        target_user_id: int,
        *,
        daily_enabled: bool = True,
        okr_enabled: bool = True,
    ) -> PersonSubscriptionOut:
        target = self._get_active_user(target_user_id)
        if target.id == self.user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot subscribe yourself")
        row = self._find_subscription(target.id, include_deleted=True)
        if row is None:
            row = Subscription(
                subscriber_id=self.user.id,
                target_user_id=target.id,
                daily_enabled=daily_enabled,
                okr_enabled=okr_enabled,
                created_by=self.user.id,
                updated_by=self.user.id,
            )
            self.db.add(row)
        else:
            row.daily_enabled = row.daily_enabled or daily_enabled
            row.okr_enabled = row.okr_enabled or okr_enabled
            row.deleted_at = None
            row.updated_by = self.user.id
            row.updated_at = utcnow()
        self.db.commit()
        return self._subscription_state(target.id)

    def unsubscribe_person(self, target_user_id: int) -> None:
        row = self.db.scalar(
            select(Subscription).where(
                Subscription.subscriber_id == self.user.id,
                Subscription.target_user_id == target_user_id,
                Subscription.deleted_at.is_(None),
            )
        )
        if row is None:
            return
        row.daily_enabled = False
        row.okr_enabled = False
        row.deleted_at = utcnow()
        row.updated_by = self.user.id
        self.db.commit()

    def update_my_signature(self, payload: PersonSignatureUpdate) -> PersonProfileOut:
        value = (payload.profile_signature or "").strip()
        if len(value) > 200:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Signature is too long")
        self.user.profile_signature = value or None
        self.user.updated_by = self.user.id
        self.db.commit()
        self.db.refresh(self.user)
        return self.get_profile(self.user.id, local_today().strftime("%Y-%m"))

    async def upload_my_avatar(self, file: UploadFile) -> PersonProfileOut:
        content = await file.read(MAX_AVATAR_BYTES + 1)
        if len(content) > MAX_AVATAR_BYTES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Avatar file is too large")
        try:
            suffix = validate_raster_image(
                content,
                filename=file.filename,
                content_type=file.content_type,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        AVATAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"user-avatar-{self.user.id}-{utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}{suffix}"
        path = AVATAR_UPLOAD_DIR / filename
        path.write_bytes(content)

        previous_url = self.user.avatar_url
        self.user.avatar_url = f"/uploads/avatars/{filename}"
        self.user.updated_by = self.user.id
        try:
            self.db.commit()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        self.db.refresh(self.user)
        delete_managed_upload(previous_url, "/uploads/avatars/", AVATAR_UPLOAD_DIR)
        return self.get_profile(self.user.id, local_today().strftime("%Y-%m"))

    def _get_active_user(self, user_id: int) -> User:
        user = self.db.get(User, user_id)
        if user is None or user.deleted_at is not None or user.status != "active":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return user

    def _subscription_state(self, target_user_id: int) -> PersonSubscriptionOut:
        if target_user_id == self.user.id:
            return PersonSubscriptionOut(subscribed=False, daily_enabled=False, okr_enabled=False)
        row = self._find_subscription(target_user_id)
        daily_enabled = bool(row and row.daily_enabled)
        okr_enabled = bool(row and row.okr_enabled)
        return PersonSubscriptionOut(
            subscribed=daily_enabled or okr_enabled,
            daily_enabled=daily_enabled,
            okr_enabled=okr_enabled,
        )

    def _empty_score(self) -> PersonAiScoreOut:
        return PersonAiScoreOut(status="not_ready")

    def _latest_daily_score(self, target_user_id: int) -> PersonAiScoreOut:
        from app.models.ai import DailyScore

        row = self.db.scalar(
            select(DailyScore)
            .where(DailyScore.user_id == target_user_id, DailyScore.deleted_at.is_(None))
            .order_by(DailyScore.score_date.desc())
            .limit(1)
        )
        if row is None:
            return PersonAiScoreOut(status="not_ready")
        return PersonAiScoreOut(
            status="ready",
            score=row.total_score,
            summary=row.one_line_review,
            updated_at=row.generated_at,
        )

    def _latest_okr_review(self, target_user_id: int) -> PersonAiScoreOut:
        from app.models.ai import OkrReview

        row = self.db.scalar(
            select(OkrReview)
            .where(OkrReview.user_id == target_user_id, OkrReview.deleted_at.is_(None))
            .order_by(OkrReview.month.desc())
            .limit(1)
        )
        if row is None:
            return PersonAiScoreOut(status="not_ready")
        return PersonAiScoreOut(
            status="ready",
            score=int(row.quality_score) if row.quality_score is not None else None,
            summary=row.summary,
            updated_at=row.generated_at,
        )

    def _social_counts(self, target_user_id: int) -> PersonSocialOut:
        enabled = or_(Subscription.daily_enabled.is_(True), Subscription.okr_enabled.is_(True))
        subscriber = aliased(User)
        followed_user = aliased(User)
        followers = self.db.scalar(
            select(func.count(distinct(Subscription.subscriber_id)))
            .join(subscriber, subscriber.id == Subscription.subscriber_id)
            .where(
                Subscription.target_user_id == target_user_id,
                Subscription.deleted_at.is_(None),
                enabled,
                subscriber.status == "active",
                subscriber.deleted_at.is_(None),
            )
        )
        following = self.db.scalar(
            select(func.count(distinct(Subscription.target_user_id)))
            .join(followed_user, followed_user.id == Subscription.target_user_id)
            .where(
                Subscription.subscriber_id == target_user_id,
                Subscription.deleted_at.is_(None),
                enabled,
                followed_user.status == "active",
                followed_user.deleted_at.is_(None),
            )
        )
        return PersonSocialOut(
            followers_count=int(followers or 0),
            following_count=int(following or 0),
        )

    def _daily_calendar(self, target_user_id: int, month: str) -> PersonMonthlyDailyOut:
        try:
            start, end = month_bounds(month)
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        task_visibility = (
            true()
            if target_user_id == self.user.id
            else DailyTask.is_private.is_(False)
        )
        rows = self.db.execute(
            select(DailyReport.report_date, func.count(DailyTask.id), func.count(ProblemSolution.id))
            .outerjoin(
                DailyTask,
                (DailyTask.report_id == DailyReport.id)
                & (DailyTask.deleted_at.is_(None))
                & task_visibility,
            )
            .outerjoin(
                ProblemSolution,
                (ProblemSolution.report_id == DailyReport.id) & (ProblemSolution.deleted_at.is_(None)),
            )
            .where(
                DailyReport.user_id == target_user_id,
                DailyReport.report_date >= start,
                DailyReport.report_date <= end,
                DailyReport.deleted_at.is_(None),
            )
            .group_by(DailyReport.report_date)
        ).all()
        content_dates = {row[0] for row in rows if row[1] or row[2]}

        today = local_today()
        days: list[PersonCalendarDayOut] = []
        current = start
        while current <= end:
            is_workday = current.weekday() < 5
            is_future = current > today
            has_daily = current in content_dates
            if is_workday and not is_future and has_daily:
                state = "done"
            elif is_workday and not is_future:
                state = "missing"
            else:
                state = "none"
            days.append(
                PersonCalendarDayOut(
                    date=current,
                    is_workday=is_workday,
                    is_future=is_future,
                    has_daily=has_daily,
                    state=state,
                )
            )
            current += timedelta(days=1)

        done_days = sum(1 for day in days if day.state == "done")
        missing_days = sum(1 for day in days if day.state == "missing")
        completed_tasks, total_tasks = self._monthly_task_counts(target_user_id, start, end)
        return PersonMonthlyDailyOut(
            month=month,
            done_days=done_days,
            missing_days=missing_days,
            required_days=done_days + missing_days,
            task_completion_rate=round(completed_tasks / total_tasks, 4) if total_tasks else None,
            completed_tasks=completed_tasks,
            total_tasks=total_tasks,
            days=days,
        )

    def _department_name(self, department_id: int | None) -> str | None:
        if department_id is None:
            return None
        return self.db.scalar(
            select(Department.name).where(
                Department.id == department_id,
                Department.deleted_at.is_(None),
            )
        )

    def _monthly_task_counts(self, target_user_id: int, start: date, end: date) -> tuple[int, int]:
        today = local_today()
        include_today = local_now().time() >= time(hour=20)
        cutoff = min(end, today if include_today else today - timedelta(days=1))
        if cutoff < start:
            return 0, 0

        included_days: list[date] = []
        current = start
        while current <= cutoff:
            if current.weekday() < 5:
                included_days.append(current)
            current += timedelta(days=1)
        if not included_days:
            return 0, 0

        task_visibility = (
            true()
            if target_user_id == self.user.id
            else DailyTask.is_private.is_(False)
        )
        row = self.db.execute(
            select(
                func.count(DailyTask.id),
                func.sum(case((DailyTask.is_done.is_(True), 1), else_=0)),
            )
            .join(DailyReport, DailyReport.id == DailyTask.report_id)
            .where(
                DailyReport.user_id == target_user_id,
                DailyReport.report_date.in_(included_days),
                DailyReport.deleted_at.is_(None),
                DailyTask.deleted_at.is_(None),
                task_visibility,
            )
        ).one()
        total = int(row[0] or 0)
        completed = int(row[1] or 0)
        return completed, total

    def _find_subscription(self, target_user_id: int, include_deleted: bool = False) -> Subscription | None:
        active = self.db.scalar(
            select(Subscription).where(
                Subscription.subscriber_id == self.user.id,
                Subscription.target_user_id == target_user_id,
                Subscription.deleted_at.is_(None),
            )
        )
        if active is not None or not include_deleted:
            return active
        return self.db.scalar(
            select(Subscription)
            .where(
                Subscription.subscriber_id == self.user.id,
                Subscription.target_user_id == target_user_id,
            )
            .order_by(Subscription.id.desc())
        )
