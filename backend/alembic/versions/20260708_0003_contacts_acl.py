"""add feishu contact sync fields and resource acl roles

Revision ID: 20260708_0003
Revises: 20260708_0002
Create Date: 2026-07-08 16:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260708_0003"
down_revision: str | None = "20260708_0002"
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
    op.add_column("departments", sa.Column("feishu_department_id", sa.String(length=80), nullable=True))
    op.add_column("departments", sa.Column("last_synced_at", sa.DateTime(), nullable=True))
    op.create_index(
        "ix_departments_feishu_department_id",
        "departments",
        ["feishu_department_id"],
        unique=True,
    )

    op.add_column(
        "users",
        sa.Column("sync_source", sa.String(length=30), nullable=False, server_default="feishu"),
    )
    op.add_column("users", sa.Column("last_synced_at", sa.DateTime(), nullable=True))
    op.add_column("users", sa.Column("disabled_reason", sa.String(length=200), nullable=True))

    op.create_table(
        "contact_sync_logs",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="running"),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("disabled_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        *audit_columns(),
    )

    # Old "editor" meant full metric management. In the new role model,
    # manager keeps that behavior; editor is data-entry only.
    op.execute("UPDATE traffic_metric_members SET role = 'manager' WHERE role = 'editor'")


def downgrade() -> None:
    op.execute("UPDATE traffic_metric_members SET role = 'editor' WHERE role = 'manager'")
    op.drop_table("contact_sync_logs")
    op.drop_column("users", "disabled_reason")
    op.drop_column("users", "last_synced_at")
    op.drop_column("users", "sync_source")
    op.drop_index("ix_departments_feishu_department_id", table_name="departments")
    op.drop_column("departments", "last_synced_at")
    op.drop_column("departments", "feishu_department_id")
