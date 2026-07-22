"""add monthly report AI scores

Revision ID: 20260710_0019
Revises: 20260710_0018
Create Date: 2026-07-10 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_0019"
down_revision: str | None = "20260710_0018"
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
        "monthly_report_scores",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("dimensions_json", sa.Text(), nullable=True),
        sa.Column("doubts_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("suggestions_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("ai_task_id", BIGINT, nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        *audit_columns(),
    )
    op.create_index(
        "uq_monthly_report_scores_user_month_active",
        "monthly_report_scores",
        ["user_id", "month"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_monthly_report_scores_user_month_active",
        table_name="monthly_report_scores",
    )
    op.drop_table("monthly_report_scores")
