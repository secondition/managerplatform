from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.db.types import BigInt, JSONText


class Notification(Base, TimestampMixin, AuditMixin):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_recipient_created", "recipient_id", "created_at"),
        Index("ix_notifications_recipient_unread", "recipient_id", "read_at"),
        Index("uq_notifications_dedupe_key", "dedupe_key", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    actor_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    type: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    action_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    entity_id: Mapped[int | None] = mapped_column(BigInt, nullable=True)
    metadata_json: Mapped[dict | list | None] = mapped_column(JSONText, nullable=True)
    dedupe_key: Mapped[str] = mapped_column(String(255), nullable=False)
    in_app_visible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    recipient = relationship("User", foreign_keys=[recipient_id])
    actor = relationship("User", foreign_keys=[actor_id])
    deliveries: Mapped[list["NotificationDelivery"]] = relationship(
        back_populates="notification",
        cascade="all, delete-orphan",
    )


class NotificationDelivery(Base, TimestampMixin, AuditMixin):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint("notification_id", "channel", name="uq_notification_delivery_channel"),
        Index("ix_notification_deliveries_due", "status", "next_attempt_at"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    notification_id: Mapped[int] = mapped_column(
        ForeignKey("notifications.id"), nullable=False
    )
    channel: Mapped[str] = mapped_column(String(30), nullable=False)
    receive_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    receive_id_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(default=0, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    notification: Mapped[Notification] = relationship(back_populates="deliveries")


class NotificationChannelRule(Base, TimestampMixin, AuditMixin):
    __tablename__ = "notification_channel_rules"
    __table_args__ = (
        Index(
            "uq_notification_channel_rules_type",
            "notification_type",
            unique=True,
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    notification_type: Mapped[str] = mapped_column(String(80), nullable=False)
    in_app_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    feishu_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
