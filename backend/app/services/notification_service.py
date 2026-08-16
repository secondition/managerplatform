from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import utcnow
from app.models.notification import Notification, NotificationChannelRule, NotificationDelivery
from app.models.user import User
from app.services.notification_catalog import NOTIFICATION_TYPE_MAP, NOTIFICATION_TYPES


@dataclass(frozen=True)
class NotificationChannels:
    in_app_enabled: bool
    feishu_enabled: bool


class NotificationService:
    def __init__(self, db: Session, actor: User | None = None) -> None:
        self.db = db
        self.actor = actor

    def channels_for(self, notification_type: str) -> NotificationChannels:
        definition = NOTIFICATION_TYPE_MAP.get(notification_type)
        if definition is None:
            raise ValueError(f"Unknown notification type: {notification_type}")
        row = self.db.scalar(
            select(NotificationChannelRule).where(
                NotificationChannelRule.notification_type == notification_type,
                NotificationChannelRule.deleted_at.is_(None),
            )
        )
        if row is None:
            return NotificationChannels(definition.in_app_default, definition.feishu_default)
        return NotificationChannels(row.in_app_enabled, row.feishu_enabled)

    def notify(
        self,
        *,
        recipient: User,
        notification_type: str,
        title: str,
        body: str,
        dedupe_key: str,
        action_url: str | None = None,
        actor_id: int | None = None,
        entity_type: str | None = None,
        entity_id: int | None = None,
        metadata: dict | list | None = None,
    ) -> Notification | None:
        channels = self.channels_for(notification_type)
        feishu_delivery_enabled = (
            channels.feishu_enabled and settings.feishu_notification_enabled
        )
        if not channels.in_app_enabled and not feishu_delivery_enabled:
            return None
        pending = next(
            (
                item
                for item in self.db.new
                if isinstance(item, Notification) and item.dedupe_key == dedupe_key
            ),
            None,
        )
        if pending is not None:
            return pending
        existing = self.db.scalar(
            select(Notification).where(
                Notification.dedupe_key == dedupe_key,
                Notification.deleted_at.is_(None),
            )
        )
        if existing is not None:
            return existing

        audit_user_id = self.actor.id if self.actor else actor_id
        row = Notification(
            recipient_id=recipient.id,
            actor_id=actor_id,
            type=notification_type,
            title=title,
            body=body,
            action_url=action_url,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata_json=metadata,
            dedupe_key=dedupe_key,
            in_app_visible=channels.in_app_enabled,
            created_by=audit_user_id,
            updated_by=audit_user_id,
        )
        self.db.add(row)
        if feishu_delivery_enabled:
            receive_id = recipient.feishu_message_receive_id
            receive_id_type = recipient.feishu_message_receive_id_type
            delivery = NotificationDelivery(
                notification=row,
                channel="feishu",
                receive_id=receive_id,
                receive_id_type=receive_id_type,
                status="pending" if receive_id and receive_id_type else "failed",
                last_error=None if receive_id and receive_id_type else "Feishu message receiver is not synced",
                created_by=audit_user_id,
                updated_by=audit_user_id,
            )
            self.db.add(delivery)
        return row

    def list_rules(self) -> list[dict]:
        rows = {
            row.notification_type: row
            for row in self.db.scalars(
                select(NotificationChannelRule).where(
                    NotificationChannelRule.deleted_at.is_(None)
                )
            ).all()
        }
        return [
            {
                "notification_type": definition.type,
                "label": definition.label,
                "description": definition.description,
                "in_app_enabled": rows.get(definition.type).in_app_enabled
                if definition.type in rows
                else definition.in_app_default,
                "feishu_enabled": rows.get(definition.type).feishu_enabled
                if definition.type in rows
                else definition.feishu_default,
                "feishu_available": settings.feishu_notification_enabled,
            }
            for definition in NOTIFICATION_TYPES
        ]

    def update_rule(
        self,
        notification_type: str,
        *,
        in_app_enabled: bool | None,
        feishu_enabled: bool | None,
    ) -> dict:
        definition = NOTIFICATION_TYPE_MAP.get(notification_type)
        if definition is None:
            raise KeyError(notification_type)
        row = self.db.scalar(
            select(NotificationChannelRule).where(
                NotificationChannelRule.notification_type == notification_type,
                NotificationChannelRule.deleted_at.is_(None),
            )
        )
        if row is None:
            row = NotificationChannelRule(
                notification_type=notification_type,
                in_app_enabled=definition.in_app_default,
                feishu_enabled=definition.feishu_default,
                created_by=self.actor.id if self.actor else None,
            )
            self.db.add(row)
        if in_app_enabled is not None:
            row.in_app_enabled = in_app_enabled
        if feishu_enabled is not None:
            row.feishu_enabled = feishu_enabled
            if not feishu_enabled:
                deliveries = self.db.scalars(
                    select(NotificationDelivery)
                    .join(Notification)
                    .where(
                        Notification.type == notification_type,
                        NotificationDelivery.channel == "feishu",
                        NotificationDelivery.status.in_(("pending", "retry")),
                        NotificationDelivery.deleted_at.is_(None),
                    )
                ).all()
                for delivery in deliveries:
                    delivery.status = "cancelled"
                    delivery.last_error = "Channel disabled by administrator"
                    delivery.updated_by = self.actor.id if self.actor else None
        row.updated_by = self.actor.id if self.actor else None
        self.db.commit()
        return {
            "notification_type": definition.type,
            "label": definition.label,
            "description": definition.description,
            "in_app_enabled": row.in_app_enabled,
            "feishu_enabled": row.feishu_enabled,
            "feishu_available": settings.feishu_notification_enabled,
        }

    def delivery_summary(self) -> dict:
        counts = dict(
            self.db.execute(
                select(NotificationDelivery.status, func.count(NotificationDelivery.id))
                .where(NotificationDelivery.deleted_at.is_(None))
                .group_by(NotificationDelivery.status)
            ).all()
        )
        errors = self.db.scalars(
            select(NotificationDelivery.last_error)
            .where(
                NotificationDelivery.status.in_(("retry", "failed")),
                NotificationDelivery.last_error.is_not(None),
                NotificationDelivery.deleted_at.is_(None),
            )
            .order_by(NotificationDelivery.updated_at.desc())
            .limit(5)
        ).all()
        return {
            "pending": counts.get("pending", 0),
            "retry": counts.get("retry", 0),
            "sent": counts.get("sent", 0),
            "failed": counts.get("failed", 0),
            "cancelled": counts.get("cancelled", 0),
            "latest_errors": list(errors),
        }


def serialize_notification(row: Notification) -> dict:
    return {
        "id": row.id,
        "type": row.type,
        "title": row.title,
        "body": row.body,
        "action_url": row.action_url,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "metadata": row.metadata_json,
        "read_at": row.read_at,
        "created_at": row.created_at,
    }
