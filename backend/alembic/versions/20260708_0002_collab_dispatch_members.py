"""add task collaborators, dispatch by, traffic metric members

Revision ID: 20260708_0002
Revises: 20260706_0001
Create Date: 2026-07-08 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260708_0002"
down_revision: str | None = "20260706_0001"
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
    # SQLite can't ALTER-add a FK constraint; add a plain column (the ORM still
    # declares the FK for other dialects / metadata).
    op.add_column("daily_tasks", sa.Column("assigned_by", BIGINT, nullable=True))

    op.create_table(
        "daily_task_collaborators",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("task_id", BIGINT, sa.ForeignKey("daily_tasks.id"), nullable=False),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        *audit_columns(),
        sa.UniqueConstraint("task_id", "user_id", name="uq_daily_task_collaborators_task_user"),
    )

    op.create_table(
        "traffic_metric_members",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("metric_id", BIGINT, sa.ForeignKey("traffic_metrics.id"), nullable=False),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"),
        *audit_columns(),
        sa.UniqueConstraint("metric_id", "user_id", name="uq_metric_member"),
    )


def downgrade() -> None:
    op.drop_table("traffic_metric_members")
    op.drop_table("daily_task_collaborators")
    op.drop_column("daily_tasks", "assigned_by")
