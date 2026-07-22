"""prompt_configs: add variables_json (selectable data sources)

Revision ID: 20260710_0013
Revises: 20260710_0012
Create Date: 2026-07-10 14:00:00.000000
"""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.services.ai.defaults import DEFAULT_VARIABLES

revision: str = "20260710_0013"
down_revision: str | None = "20260710_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "prompt_configs",
        sa.Column("variables_json", sa.Text(), nullable=False, server_default="[]"),
    )
    # Backfill each existing row with its prompt type's default (all) variables.
    conn = op.get_bind()
    for prompt_type, keys in DEFAULT_VARIABLES.items():
        conn.exec_driver_sql(
            "UPDATE prompt_configs SET variables_json = ? WHERE prompt_type = ?",
            (json.dumps(keys), prompt_type),
        )


def downgrade() -> None:
    with op.batch_alter_table("prompt_configs") as batch:
        batch.drop_column("variables_json")
