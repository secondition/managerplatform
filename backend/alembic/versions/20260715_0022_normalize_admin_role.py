"""normalize legacy role=admin to member

Revision ID: 20260715_0022
Revises: 20260715_0021
Create Date: 2026-07-15 20:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260715_0022"
down_revision: str | None = "20260715_0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # role=admin was never used for authorization (permission rows + owner
    # bypass are the source of truth). Collapse any leftover admin roles.
    op.execute("UPDATE users SET role = 'member' WHERE role = 'admin'")


def downgrade() -> None:
    # Irreversible by design: we no longer distinguish admin role.
    pass