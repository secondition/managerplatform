"""upgrade daily suggestions to structured action recommendations

Revision ID: 20260710_0017
Revises: 20260710_0016
Create Date: 2026-07-10 19:00:00.000000
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.services.ai.defaults import DEFAULT_TEMPLATES, DEFAULT_VARIABLES

revision: str = "20260710_0017"
down_revision: str | None = "20260710_0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "daily_suggestions",
        sa.Column("suggestion_type", sa.String(length=10), nullable=False, server_default="amber"),
    )
    op.add_column(
        "daily_suggestions",
        sa.Column("linked_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "daily_suggestions",
        sa.Column("needs_info", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "daily_suggestions",
        sa.Column("ask_json", sa.Text(), nullable=False, server_default="{}"),
    )

    conn = op.get_bind()
    conn.exec_driver_sql(
        "UPDATE prompt_configs SET template_content = ?, variables_json = ?, version = ? "
        "WHERE prompt_type = ?",
        (
            DEFAULT_TEMPLATES["daily_suggestion"],
            json.dumps(DEFAULT_VARIABLES["daily_suggestion"], ensure_ascii=False),
            "v1",
            "daily_suggestion",
        ),
    )


def downgrade() -> None:
    with op.batch_alter_table("daily_suggestions") as batch:
        batch.drop_column("ask_json")
        batch.drop_column("needs_info")
        batch.drop_column("linked_json")
        batch.drop_column("suggestion_type")
