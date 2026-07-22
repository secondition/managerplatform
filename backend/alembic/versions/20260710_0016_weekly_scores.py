"""add weekly AI work-performance scores

Revision ID: 20260710_0016
Revises: 20260710_0015
Create Date: 2026-07-10 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_0016"
down_revision: str | None = "20260710_0015"
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
        "weekly_scores",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.String(length=50), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("dimensions_json", sa.Text(), nullable=True),
        sa.Column("key_achievements_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("concerns_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("manager_hint", sa.Text(), nullable=True),
        sa.Column("ai_task_id", BIGINT, nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        *audit_columns(),
    )
    op.create_index(
        "uq_weekly_scores_user_week_active",
        "weekly_scores",
        ["user_id", "week_start"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_weekly_scores_user_week_active", table_name="weekly_scores")
    op.drop_table("weekly_scores")
