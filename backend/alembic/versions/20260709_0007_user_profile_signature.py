"""add user profile signature

Revision ID: 20260709_0007
Revises: 20260709_0006
Create Date: 2026-07-09 16:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260709_0007"
down_revision: str | None = "20260709_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("profile_signature", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "profile_signature")
