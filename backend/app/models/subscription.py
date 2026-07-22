from sqlalchemy import Boolean, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.db.types import BigInt


class Subscription(Base, TimestampMixin, AuditMixin):
    __tablename__ = "subscriptions"
    __table_args__ = (
        Index(
            "uq_subscriptions_subscriber_target_active",
            "subscriber_id",
            "target_user_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_subscriptions_target_user", "target_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    subscriber_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    target_user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    daily_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    okr_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    subscriber = relationship("User", foreign_keys=[subscriber_id])
    target_user = relationship("User", foreign_keys=[target_user_id])
