"""add private visibility to daily tasks

Revision ID: 20260720_0026
Revises: 20260716_0025
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_0026"
down_revision: str | None = "20260716_0025"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "daily_tasks",
        sa.Column(
            "is_private",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade() -> None:
    op.drop_column("daily_tasks", "is_private")
