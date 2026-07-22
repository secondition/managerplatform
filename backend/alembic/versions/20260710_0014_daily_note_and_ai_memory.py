"""daily_tasks.note + ai_user_memory table + reset daily_score default template

Revision ID: 20260710_0014
Revises: 20260710_0013
Create Date: 2026-07-10 16:00:00.000000
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.services.ai.defaults import (
    DEFAULT_TEMPLATES,
    DEFAULT_VARIABLES,
)

revision: str = "20260710_0014"
down_revision: str | None = "20260710_0013"
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
    op.add_column("daily_tasks", sa.Column("note", sa.Text(), nullable=True))

    op.create_table(
        "ai_user_memory",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, nullable=False),
        sa.Column("recurring_strengths_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("recurring_issues_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("manager_hints_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("last_summary", sa.Text(), nullable=True),
        *audit_columns(),
    )
    op.create_index("ix_ai_user_memory_user_id", "ai_user_memory", ["user_id"])

    # The daily_score output shape changed (dimensions object, okr_outside object,
    # memory_update). Any prior custom template would emit an incompatible JSON, so
    # reset the daily_score row to the new default template + full variable set.
    conn = op.get_bind()
    conn.exec_driver_sql(
        "UPDATE prompt_configs SET template_content = ?, variables_json = ? "
        "WHERE prompt_type = ?",
        (
            DEFAULT_TEMPLATES["daily_score"],
            json.dumps(DEFAULT_VARIABLES["daily_score"]),
            "daily_score",
        ),
    )


def downgrade() -> None:
    op.drop_index("ix_ai_user_memory_user_id", table_name="ai_user_memory")
    op.drop_table("ai_user_memory")
    with op.batch_alter_table("daily_tasks") as batch:
        batch.drop_column("note")
