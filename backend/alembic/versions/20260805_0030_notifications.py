"""notification center, channel rules and Feishu delivery identity

Revision ID: 20260805_0030
Revises: 20260731_0029
"""

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "20260805_0030"
down_revision: str | None = "20260731_0029"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BIGINT = sa.BigInteger().with_variant(sa.Integer, "sqlite")

DEFAULT_RULES = (
    ("daily.assigned", True, True),
    ("daily.collaborator_added", True, True),
    ("subscription.started", True, True),
    ("subscription.ended", True, False),
    ("daily.score_ready", True, False),
    ("daily.suggestion_ready", True, True),
    ("weekly.score_ready", True, False),
    ("okr.review_ready", True, False),
    ("monthly_report.score_ready", True, False),
    ("daily.missing", True, True),
    ("traffic.weekly_metric_missing", True, True),
)


def upgrade() -> None:
    op.add_column("users", sa.Column("feishu_message_receive_id", sa.String(120), nullable=True))
    op.add_column(
        "users", sa.Column("feishu_message_receive_id_type", sa.String(30), nullable=True)
    )

    op.create_table(
        "notifications",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("recipient_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("actor_id", BIGINT, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("type", sa.String(80), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("action_url", sa.String(500), nullable=True),
        sa.Column("entity_type", sa.String(80), nullable=True),
        sa.Column("entity_id", BIGINT, nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("dedupe_key", sa.String(255), nullable=False),
        sa.Column("in_app_visible", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("read_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
    )
    op.create_index("ix_notifications_recipient_created", "notifications", ["recipient_id", "created_at"])
    op.create_index("ix_notifications_recipient_unread", "notifications", ["recipient_id", "read_at"])
    op.create_index("uq_notifications_dedupe_key", "notifications", ["dedupe_key"], unique=True)

    op.create_table(
        "notification_deliveries",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("notification_id", BIGINT, sa.ForeignKey("notifications.id"), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False),
        sa.Column("receive_id", sa.String(120), nullable=True),
        sa.Column("receive_id_type", sa.String(30), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
        sa.UniqueConstraint("notification_id", "channel", name="uq_notification_delivery_channel"),
    )
    op.create_index(
        "ix_notification_deliveries_due",
        "notification_deliveries",
        ["status", "next_attempt_at"],
    )

    rules = op.create_table(
        "notification_channel_rules",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("notification_type", sa.String(80), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False),
        sa.Column("feishu_enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
    )
    op.create_index(
        "uq_notification_channel_rules_type",
        "notification_channel_rules",
        ["notification_type"],
        unique=True,
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    op.bulk_insert(
        rules,
        [
            {
                "notification_type": item[0],
                "in_app_enabled": item[1],
                "feishu_enabled": item[2],
                "created_at": now,
                "updated_at": now,
            }
            for item in DEFAULT_RULES
        ],
    )


def downgrade() -> None:
    op.drop_index("uq_notification_channel_rules_type", table_name="notification_channel_rules")
    op.drop_table("notification_channel_rules")
    op.drop_index("ix_notification_deliveries_due", table_name="notification_deliveries")
    op.drop_table("notification_deliveries")
    op.drop_index("uq_notifications_dedupe_key", table_name="notifications")
    op.drop_index("ix_notifications_recipient_unread", table_name="notifications")
    op.drop_index("ix_notifications_recipient_created", table_name="notifications")
    op.drop_table("notifications")
    op.drop_column("users", "feishu_message_receive_id_type")
    op.drop_column("users", "feishu_message_receive_id")
