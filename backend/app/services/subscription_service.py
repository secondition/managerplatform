from datetime import date

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.subscription import Subscription
from app.models.user import User
from app.schemas.daily import DailyReportOut
from app.schemas.subscription import (
    DailySubscriptionCandidateOut,
    DailySubscriptionOut,
    OkrSubscriptionCandidateOut,
    OkrSubscriptionOut,
    SubscribedDailyReportOut,
    SubscribedOkrMonthOut,
)
from app.schemas.user import UserBrief
from app.services.daily_service import DailyService
from app.services.okr_service import OkrService
from app.services.notification_service import NotificationService
from app.core.security import utcnow


class SubscriptionService:
    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    def list_daily_subscriptions(self) -> list[DailySubscriptionOut]:
        rows = self.db.scalars(
            select(Subscription)
            .options(selectinload(Subscription.target_user))
            .join(User, User.id == Subscription.target_user_id)
            .where(
                Subscription.subscriber_id == self.user.id,
                self._active_relationship(),
                User.status == "active",
                User.deleted_at.is_(None),
            )
            .order_by(User.name, Subscription.id)
        ).all()
        return [self._serialize_subscription(row) for row in rows]

    def list_daily_candidates(self, q: str | None = None) -> list[DailySubscriptionCandidateOut]:
        subscribed_ids = set(
            self.db.scalars(
                select(Subscription.target_user_id).where(
                    Subscription.subscriber_id == self.user.id,
                    self._active_relationship(),
                )
            ).all()
        )
        stmt = select(User).where(
            User.id != self.user.id,
            User.status == "active",
            User.deleted_at.is_(None),
        )
        if q and q.strip():
            stmt = stmt.where(User.name.ilike(f"%{q.strip()}%"))
        users = self.db.scalars(stmt.order_by(User.name, User.id).limit(80)).all()
        return [
            DailySubscriptionCandidateOut(
                user=UserBrief.model_validate(user),
                subscribed=user.id in subscribed_ids,
            )
            for user in users
        ]

    def subscribe_daily(self, target_user_id: int) -> DailySubscriptionOut:
        row = self._subscribe_both(target_user_id)
        return self._serialize_subscription(row)

    def unsubscribe_daily(self, target_user_id: int) -> None:
        self._unsubscribe_both(target_user_id)

    def get_daily_report(self, target_user_id: int, report_date: date) -> SubscribedDailyReportOut:
        subscription = self.db.scalar(
            select(Subscription)
            .options(selectinload(Subscription.target_user))
            .join(User, User.id == Subscription.target_user_id)
            .where(
                Subscription.subscriber_id == self.user.id,
                Subscription.target_user_id == target_user_id,
                self._active_relationship(),
                User.status == "active",
                User.deleted_at.is_(None),
            )
        )
        if subscription is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
        report = DailyService(self.db, self.user).get_followed_daily_out(target_user_id, report_date)
        return self._with_target_user(report, subscription.target_user)

    def _active_relationship(self):
        """A subscription counts as active while not soft-deleted and at least
        one content flag is on. Subscribe/unsubscribe now toggle both flags
        together, so this also tolerates legacy half-subscribed rows."""
        return (
            Subscription.deleted_at.is_(None)
            & (Subscription.daily_enabled.is_(True) | Subscription.okr_enabled.is_(True))
        )

    # ---- OKR subscriptions -------------------------------------------------

    def list_okr_subscriptions(self) -> list[OkrSubscriptionOut]:
        rows = self.db.scalars(
            select(Subscription)
            .options(selectinload(Subscription.target_user))
            .join(User, User.id == Subscription.target_user_id)
            .where(
                Subscription.subscriber_id == self.user.id,
                self._active_relationship(),
                User.status == "active",
                User.deleted_at.is_(None),
            )
            .order_by(User.name, Subscription.id)
        ).all()
        return [self._serialize_okr_subscription(row) for row in rows]

    def list_okr_candidates(self, q: str | None = None) -> list[OkrSubscriptionCandidateOut]:
        subscribed_ids = set(
            self.db.scalars(
                select(Subscription.target_user_id).where(
                    Subscription.subscriber_id == self.user.id,
                    self._active_relationship(),
                )
            ).all()
        )
        stmt = select(User).where(
            User.id != self.user.id,
            User.status == "active",
            User.deleted_at.is_(None),
        )
        if q and q.strip():
            stmt = stmt.where(User.name.ilike(f"%{q.strip()}%"))
        users = self.db.scalars(stmt.order_by(User.name, User.id).limit(80)).all()
        return [
            OkrSubscriptionCandidateOut(
                user=UserBrief.model_validate(user),
                subscribed=user.id in subscribed_ids,
            )
            for user in users
        ]

    def subscribe_okr(self, target_user_id: int) -> OkrSubscriptionOut:
        row = self._subscribe_both(target_user_id)
        return self._serialize_okr_subscription(row)

    def unsubscribe_okr(self, target_user_id: int) -> None:
        self._unsubscribe_both(target_user_id)

    def get_okr_month(self, target_user_id: int, month: str) -> SubscribedOkrMonthOut:
        subscription = self.db.scalar(
            select(Subscription)
            .options(selectinload(Subscription.target_user))
            .join(User, User.id == Subscription.target_user_id)
            .where(
                Subscription.subscriber_id == self.user.id,
                Subscription.target_user_id == target_user_id,
                self._active_relationship(),
                User.status == "active",
                User.deleted_at.is_(None),
            )
        )
        if subscription is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
        month_data = OkrService(self.db, self.user).get_month_readonly(month, target_user_id)
        return SubscribedOkrMonthOut(
            **month_data,
            target_user=UserBrief.model_validate(subscription.target_user),
        )

    def _subscribe_both(self, target_user_id: int) -> Subscription:
        """Subscribe to the whole relationship (daily + OKR together).

        Subscriptions are no longer split by content type: subscribing a
        colleague grants both their daily report and OKR views at once.
        """
        target = self._get_active_target(target_user_id)
        existing = self.db.scalar(
            select(Subscription)
            .options(selectinload(Subscription.target_user))
            .where(
                Subscription.subscriber_id == self.user.id,
                Subscription.target_user_id == target.id,
                Subscription.deleted_at.is_(None),
            )
        )
        if existing is not None:
            existing.daily_enabled = True
            existing.okr_enabled = True
            existing.updated_by = self.user.id
            self.db.commit()
            self.db.refresh(existing)
            existing.target_user = target
            return existing

        row = Subscription(
            subscriber_id=self.user.id,
            target_user_id=target.id,
            daily_enabled=True,
            okr_enabled=True,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        self.db.add(row)
        self.db.flush()
        NotificationService(self.db, self.user).notify(
            recipient=target,
            actor_id=self.user.id,
            notification_type="subscription.started",
            title="新增内容订阅",
            body=f"{self.user.name} 开始订阅你的日报和 OKR。",
            action_url=f"/people/{self.user.id}",
            entity_type="subscription",
            entity_id=row.id,
            dedupe_key=f"subscription.started:{row.id}",
        )
        self.db.commit()
        self.db.refresh(row)
        row.target_user = target
        return row

    def _unsubscribe_both(self, target_user_id: int) -> None:
        """Cancel the whole relationship (daily + OKR together)."""
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
        target = self.db.get(User, target_user_id)
        if target is not None:
            NotificationService(self.db, self.user).notify(
                recipient=target,
                actor_id=self.user.id,
                notification_type="subscription.ended",
                title="内容订阅已取消",
                body=f"{self.user.name} 已取消订阅你的日报和 OKR。",
                action_url=f"/people/{self.user.id}",
                entity_type="subscription",
                entity_id=row.id,
                dedupe_key=f"subscription.ended:{row.id}:{utcnow().date().isoformat()}",
            )
        self.db.commit()

    def _get_active_target(self, target_user_id: int) -> User:
        if target_user_id == self.user.id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot subscribe yourself")
        target = self.db.get(User, target_user_id)
        if target is None or target.deleted_at is not None or target.status != "active":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return target

    def _serialize_subscription(self, row: Subscription) -> DailySubscriptionOut:
        return DailySubscriptionOut(
            id=row.id,
            target_user=UserBrief.model_validate(row.target_user),
            daily_enabled=row.daily_enabled,
            okr_enabled=row.okr_enabled,
            created_at=row.created_at,
        )

    def _serialize_okr_subscription(self, row: Subscription) -> OkrSubscriptionOut:
        return OkrSubscriptionOut(
            id=row.id,
            target_user=UserBrief.model_validate(row.target_user),
            daily_enabled=row.daily_enabled,
            okr_enabled=row.okr_enabled,
            created_at=row.created_at,
        )

    def _with_target_user(self, report: DailyReportOut, target_user: User) -> SubscribedDailyReportOut:
        return SubscribedDailyReportOut(
            id=report.id,
            user_id=report.user_id,
            report_date=report.report_date,
            status=report.status,
            tasks=report.tasks,
            problems=report.problems,
            target_user=UserBrief.model_validate(target_user),
        )
