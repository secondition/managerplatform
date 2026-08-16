"""chat send request idempotency

Revision ID: 20260812_0034
Revises: 20260812_0033
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0034"
down_revision: str | None = "20260812_0033"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BIGINT = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    op.create_table(
        "chat_send_requests",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("agent_id", BIGINT, sa.ForeignKey("ai_agents.id"), nullable=False),
        sa.Column("client_request_id", sa.String(80), nullable=False),
        sa.Column("feishu_uuid", sa.String(80), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="sending"),
        sa.Column("feishu_message_id", sa.String(120), nullable=True),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
    )
    op.create_index(
        "uq_chat_send_requests_client_active",
        "chat_send_requests",
        ["user_id", "agent_id", "client_request_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_chat_send_requests_status",
        "chat_send_requests",
        ["status", "updated_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_chat_send_requests_status", table_name="chat_send_requests")
    op.drop_index(
        "uq_chat_send_requests_client_active",
        table_name="chat_send_requests",
    )
    op.drop_table("chat_send_requests")
