"""Feishu chat synchronization projection

Revision ID: 20260812_0033
Revises: 20260812_0032
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0033"
down_revision: str | None = "20260812_0032"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BIGINT = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    op.create_table(
        "feishu_chat_sync_states",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("agent_id", BIGINT, sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("chat_id", sa.String(120), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="disabled"),
        sa.Column("sync_mode", sa.String(30), nullable=False, server_default="backfill"),
        sa.Column("backfill_start_time_ms", BIGINT, nullable=True),
        sa.Column("current_window_start_time_ms", BIGINT, nullable=True),
        sa.Column("current_window_end_time_ms", BIGINT, nullable=True),
        sa.Column("last_page_token", sa.String(500), nullable=True),
        sa.Column("last_message_create_time_ms", BIGINT, nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_message_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_member_sync_at", sa.DateTime(), nullable=True),
        sa.Column("next_sync_at", sa.DateTime(), nullable=True),
        sa.Column("rate_limited_until", sa.DateTime(), nullable=True),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
    )
    op.create_index(
        "uq_feishu_chat_sync_states_agent_chat_active",
        "feishu_chat_sync_states",
        ["agent_id", "chat_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_feishu_chat_sync_states_due",
        "feishu_chat_sync_states",
        ["status", "next_sync_at"],
    )

    op.create_table(
        "feishu_chat_messages",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("message_id", sa.String(120), nullable=False),
        sa.Column("chat_id", sa.String(120), nullable=False),
        sa.Column("sender_id", sa.String(120), nullable=True),
        sa.Column("sender_id_type", sa.String(30), nullable=True),
        sa.Column("sender_type", sa.String(30), nullable=True),
        sa.Column("msg_type", sa.String(40), nullable=False),
        sa.Column("content_json", sa.Text(), nullable=True),
        sa.Column("mentions_json", sa.Text(), nullable=True),
        sa.Column("parent_id", sa.String(120), nullable=True),
        sa.Column("root_id", sa.String(120), nullable=True),
        sa.Column("thread_id", sa.String(120), nullable=True),
        sa.Column("create_time_ms", BIGINT, nullable=False),
        sa.Column("update_time_ms", BIGINT, nullable=True),
        sa.Column("deleted", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "uq_feishu_chat_messages_message_id",
        "feishu_chat_messages",
        ["message_id"],
        unique=True,
    )
    op.create_index(
        "ix_feishu_chat_messages_chat_created",
        "feishu_chat_messages",
        ["chat_id", "create_time_ms"],
    )
    op.create_index(
        "ix_feishu_chat_messages_chat_sender_created",
        "feishu_chat_messages",
        ["chat_id", "sender_id", "create_time_ms"],
    )
    op.create_index("ix_feishu_chat_messages_parent", "feishu_chat_messages", ["parent_id"])
    op.create_index("ix_feishu_chat_messages_root", "feishu_chat_messages", ["root_id"])

    op.create_table(
        "feishu_chat_members",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("chat_id", sa.String(120), nullable=False),
        sa.Column("member_id", sa.String(120), nullable=False),
        sa.Column("member_id_type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(100), nullable=True),
        sa.Column("member_type", sa.String(30), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index(
        "uq_feishu_chat_members_identity_active",
        "feishu_chat_members",
        ["chat_id", "member_id", "member_id_type"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_feishu_chat_members_lookup",
        "feishu_chat_members",
        ["chat_id", "member_id", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_feishu_chat_members_lookup", table_name="feishu_chat_members")
    op.drop_index(
        "uq_feishu_chat_members_identity_active",
        table_name="feishu_chat_members",
    )
    op.drop_table("feishu_chat_members")
    op.drop_index("ix_feishu_chat_messages_root", table_name="feishu_chat_messages")
    op.drop_index("ix_feishu_chat_messages_parent", table_name="feishu_chat_messages")
    op.drop_index(
        "ix_feishu_chat_messages_chat_sender_created",
        table_name="feishu_chat_messages",
    )
    op.drop_index(
        "ix_feishu_chat_messages_chat_created",
        table_name="feishu_chat_messages",
    )
    op.drop_index(
        "uq_feishu_chat_messages_message_id",
        table_name="feishu_chat_messages",
    )
    op.drop_table("feishu_chat_messages")
    op.drop_index("ix_feishu_chat_sync_states_due", table_name="feishu_chat_sync_states")
    op.drop_index(
        "uq_feishu_chat_sync_states_agent_chat_active",
        table_name="feishu_chat_sync_states",
    )
    op.drop_table("feishu_chat_sync_states")
