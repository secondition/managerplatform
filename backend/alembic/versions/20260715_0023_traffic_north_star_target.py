"""add traffic north star target

Revision ID: 20260715_0023
Revises: 20260715_0022
Create Date: 2026-07-15 21:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0023"
down_revision: str | None = "20260715_0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("traffic_metrics", sa.Column("north_star_target", sa.Numeric(18, 4), nullable=True))


def downgrade() -> None:
    op.drop_column("traffic_metrics", "north_star_target")
