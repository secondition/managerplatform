"""add okr objectives, key results and monthly report sections

Revision ID: 20260709_0009
Revises: 20260709_0008
Create Date: 2026-07-09 18:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260709_0009"
down_revision: str | None = "20260709_0008"
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
        "okr_objectives",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("progress", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("score", sa.Numeric(5, 2), nullable=True),
        sa.Column("ai_comment", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *audit_columns(),
    )
    op.create_index(
        "ix_okr_objectives_user_month", "okr_objectives", ["user_id", "month"]
    )

    op.create_table(
        "okr_key_results",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("objective_id", BIGINT, sa.ForeignKey("okr_objectives.id"), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("start_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("target_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("current_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("weight", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("progress", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="normal"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *audit_columns(),
    )

    op.create_table(
        "monthly_report_sections",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("section_key", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=100), nullable=False),
        sa.Column("content_html", sa.Text(), nullable=True),
        sa.Column("content_json", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *audit_columns(),
        sa.UniqueConstraint(
            "user_id", "month", "section_key", name="uq_monthly_report_section"
        ),
    )


def downgrade() -> None:
    op.drop_table("monthly_report_sections")
    op.drop_table("okr_key_results")
    op.drop_index("ix_okr_objectives_user_month", table_name="okr_objectives")
    op.drop_table("okr_objectives")
