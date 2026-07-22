"""prompt_configs: drop unused enabled, change version to editable string

Revision ID: 20260710_0011
Revises: 20260710_0010
Create Date: 2026-07-10 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_0011"
down_revision: str | None = "20260710_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # SQLite needs batch mode for column drops / type changes.
    with op.batch_alter_table("prompt_configs") as batch:
        batch.drop_column("enabled")
        batch.alter_column(
            "version",
            existing_type=sa.Integer(),
            type_=sa.String(length=50),
            existing_nullable=False,
            server_default="v1",
        )


def downgrade() -> None:
    with op.batch_alter_table("prompt_configs") as batch:
        batch.alter_column(
            "version",
            existing_type=sa.String(length=50),
            type_=sa.Integer(),
            existing_nullable=False,
            server_default="1",
        )
        batch.add_column(
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true())
        )
