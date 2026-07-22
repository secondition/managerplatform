"""cleanup OKR and traffic-light schemas

Revision ID: 20260715_0024
Revises: 20260715_0023
Create Date: 2026-07-15 22:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260715_0024"
down_revision: str | None = "20260715_0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE okr_objectives
        SET progress = COALESCE(
            (
                SELECT AVG(progress)
                FROM okr_key_results
                WHERE okr_key_results.objective_id = okr_objectives.id
                  AND okr_key_results.deleted_at IS NULL
            ),
            0
        )
        WHERE deleted_at IS NULL
        """
    )
    op.execute("UPDATE traffic_metric_members SET role = 'editor' WHERE role = 'manager'")

    with op.batch_alter_table("okr_objectives") as batch:
        batch.drop_column("description")

    with op.batch_alter_table("okr_key_results") as batch:
        batch.drop_column("start_value")
        batch.drop_column("target_value")
        batch.drop_column("current_value")
        batch.drop_column("unit")
        batch.drop_column("weight")
        batch.drop_column("status")

    with op.batch_alter_table("okr_key_result_progress") as batch:
        batch.drop_column("current_value")
        batch.drop_column("progress")

    with op.batch_alter_table("traffic_metrics") as batch:
        batch.drop_column("category")
        batch.drop_column("range_min")
        batch.drop_column("range_max")
        batch.drop_column("is_north_star")


def downgrade() -> None:
    with op.batch_alter_table("traffic_metrics") as batch:
        batch.add_column(sa.Column("is_north_star", sa.Boolean(), nullable=False, server_default=sa.false()))
        batch.add_column(sa.Column("range_max", sa.Numeric(18, 4), nullable=True))
        batch.add_column(sa.Column("range_min", sa.Numeric(18, 4), nullable=True))
        batch.add_column(sa.Column("category", sa.String(length=100), nullable=True))

    with op.batch_alter_table("okr_key_result_progress") as batch:
        batch.add_column(sa.Column("progress", sa.Numeric(5, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("current_value", sa.Numeric(18, 4), nullable=False, server_default="0"))

    with op.batch_alter_table("okr_key_results") as batch:
        batch.add_column(sa.Column("status", sa.String(length=20), nullable=False, server_default="normal"))
        batch.add_column(sa.Column("weight", sa.Numeric(5, 2), nullable=False, server_default="0"))
        batch.add_column(sa.Column("unit", sa.String(length=30), nullable=True))
        batch.add_column(sa.Column("current_value", sa.Numeric(18, 4), nullable=False, server_default="0"))
        batch.add_column(sa.Column("target_value", sa.Numeric(18, 4), nullable=False, server_default="0"))
        batch.add_column(sa.Column("start_value", sa.Numeric(18, 4), nullable=False, server_default="0"))

    with op.batch_alter_table("okr_objectives") as batch:
        batch.add_column(sa.Column("description", sa.Text(), nullable=True))
