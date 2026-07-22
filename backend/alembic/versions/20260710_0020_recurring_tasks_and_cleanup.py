"""materialize recurring tasks and clean obsolete OKR fields

Revision ID: 20260710_0020
Revises: 20260710_0019
Create Date: 2026-07-10 22:00:00.000000
"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_0020"
down_revision: str | None = "20260710_0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "daily_tasks", sa.Column("repeat_series_id", sa.String(length=36), nullable=True)
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT daily_tasks.id FROM daily_tasks "
            "JOIN daily_reports ON daily_reports.id = daily_tasks.report_id "
            "WHERE daily_tasks.repeat_rule IN ('daily', 'weekly') "
            "AND daily_tasks.deleted_at IS NULL "
            "AND daily_reports.deleted_at IS NULL "
            "AND daily_reports.report_date >= date('now', '-7 days')"
        )
    ).all()
    for row in rows:
        connection.execute(
            sa.text("UPDATE daily_tasks SET repeat_series_id = :series_id WHERE id = :task_id"),
            {"series_id": str(uuid4()), "task_id": row.id},
        )
    op.create_index(
        "uq_daily_tasks_repeat_series_report_active",
        "daily_tasks",
        ["repeat_series_id", "report_id"],
        unique=True,
        sqlite_where=sa.text("repeat_series_id IS NOT NULL AND deleted_at IS NULL"),
    )

    connection.exec_driver_sql(
        "UPDATE user_permissions SET deleted_at = CURRENT_TIMESTAMP "
        "WHERE id IN ("
        "SELECT id FROM ("
        "SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id, permission ORDER BY id) AS rn "
        "FROM user_permissions WHERE deleted_at IS NULL"
        ") WHERE rn > 1)"
    )
    connection.exec_driver_sql(
        "UPDATE ai_user_memory SET deleted_at = CURRENT_TIMESTAMP "
        "WHERE id IN ("
        "SELECT id FROM ("
        "SELECT id, ROW_NUMBER() OVER (PARTITION BY user_id ORDER BY id) AS rn "
        "FROM ai_user_memory WHERE deleted_at IS NULL"
        ") WHERE rn > 1)"
    )
    op.create_index(
        "uq_user_permissions_user_permission_active",
        "user_permissions",
        ["user_id", "permission"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_ai_user_memory_user_active",
        "ai_user_memory",
        ["user_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    with op.batch_alter_table("okr_objectives") as batch:
        batch.drop_column("ai_comment")
        batch.drop_column("score")


def downgrade() -> None:
    with op.batch_alter_table("okr_objectives") as batch:
        batch.add_column(sa.Column("score", sa.Numeric(5, 2), nullable=True))
        batch.add_column(sa.Column("ai_comment", sa.Text(), nullable=True))
    op.drop_index("uq_ai_user_memory_user_active", table_name="ai_user_memory")
    op.drop_index(
        "uq_user_permissions_user_permission_active", table_name="user_permissions"
    )
    op.drop_index(
        "uq_daily_tasks_repeat_series_report_active", table_name="daily_tasks"
    )
    with op.batch_alter_table("daily_tasks") as batch:
        batch.drop_column("repeat_series_id")
