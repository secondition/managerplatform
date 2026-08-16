"""Feishu user credentials

Revision ID: 20260812_0032
Revises: 20260812_0031
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260812_0032"
down_revision: str | None = "20260812_0031"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BIGINT = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    op.create_table(
        "feishu_user_credentials",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("access_token_encrypted", sa.Text(), nullable=True),
        sa.Column("access_token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("refresh_token_encrypted", sa.Text(), nullable=True),
        sa.Column("refresh_token_expires_at", sa.DateTime(), nullable=True),
        sa.Column("granted_scopes_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="active"),
        sa.Column("refresh_lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("last_refreshed_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
    )
    op.create_index(
        "uq_feishu_user_credentials_user_active",
        "feishu_user_credentials",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "ix_feishu_user_credentials_status",
        "feishu_user_credentials",
        ["status", "access_token_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_feishu_user_credentials_status", table_name="feishu_user_credentials")
    op.drop_index(
        "uq_feishu_user_credentials_user_active",
        table_name="feishu_user_credentials",
    )
    op.drop_table("feishu_user_credentials")
