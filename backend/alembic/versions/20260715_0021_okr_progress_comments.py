"""add OKR progress history and comments

Revision ID: 20260715_0021
Revises: 20260710_0020
Create Date: 2026-07-15 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0021"
down_revision: str | None = "20260710_0020"
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
        "okr_key_result_progress",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("key_result_id", BIGINT, sa.ForeignKey("okr_key_results.id"), nullable=False),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("progress_date", sa.Date(), nullable=False),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column("current_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("progress", sa.Numeric(5, 2), nullable=False),
        *audit_columns(),
    )
    op.create_index(
        "ix_okr_kr_progress_kr_date",
        "okr_key_result_progress",
        ["key_result_id", "progress_date"],
    )

    op.create_table(
        "okr_comments",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("objective_id", BIGINT, sa.ForeignKey("okr_objectives.id"), nullable=True),
        sa.Column("key_result_id", BIGINT, sa.ForeignKey("okr_key_results.id"), nullable=True),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        *audit_columns(),
        sa.CheckConstraint(
            "(objective_id IS NOT NULL AND key_result_id IS NULL) OR "
            "(objective_id IS NULL AND key_result_id IS NOT NULL)",
            name="ck_okr_comments_exactly_one_target",
        ),
    )
    op.create_index("ix_okr_comments_objective", "okr_comments", ["objective_id"])
    op.create_index("ix_okr_comments_key_result", "okr_comments", ["key_result_id"])


def downgrade() -> None:
    op.drop_index("ix_okr_comments_key_result", table_name="okr_comments")
    op.drop_index("ix_okr_comments_objective", table_name="okr_comments")
    op.drop_table("okr_comments")
    op.drop_index("ix_okr_kr_progress_kr_date", table_name="okr_key_result_progress")
    op.drop_table("okr_key_result_progress")
