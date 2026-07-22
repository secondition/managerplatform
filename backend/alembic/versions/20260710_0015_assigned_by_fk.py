"""add missing daily task assigned_by foreign key

Revision ID: 20260710_0015
Revises: 20260710_0014
Create Date: 2026-07-10 17:00:00.000000
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260710_0015"
down_revision: str | None = "20260710_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("daily_tasks") as batch:
        batch.create_foreign_key(
            "fk_daily_tasks_assigned_by_users",
            "users",
            ["assigned_by"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("daily_tasks") as batch:
        batch.drop_constraint("fk_daily_tasks_assigned_by_users", type_="foreignkey")
