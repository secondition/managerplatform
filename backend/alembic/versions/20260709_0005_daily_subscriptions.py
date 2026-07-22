"""add daily subscriptions

Revision ID: 20260709_0005
Revises: 20260709_0004
Create Date: 2026-07-09 10:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260709_0005"
down_revision: str | None = "20260709_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BIGINT = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
    ]


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("subscriber_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("target_user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("daily_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("okr_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        *audit_columns(),
    )
    op.create_index(
        "uq_subscriptions_subscriber_target_active",
        "subscriptions",
        ["subscriber_id", "target_user_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_subscriptions_target_user", "subscriptions", ["target_user_id"])


def downgrade() -> None:
    op.drop_index("ix_subscriptions_target_user", table_name="subscriptions")
    op.drop_index("uq_subscriptions_subscriber_target_active", table_name="subscriptions")
    op.drop_table("subscriptions")
