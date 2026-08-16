"""remove traffic legacy data and require assignment values

Revision ID: 20260731_0029
Revises: 20260729_0028
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_0029"
down_revision: str | None = "20260729_0028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BIGINT = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text("DELETE FROM traffic_metric_values"))
    connection.execute(sa.text("DELETE FROM traffic_metric_members"))
    connection.execute(sa.text("DELETE FROM traffic_metric_assignments"))
    connection.execute(sa.text("DELETE FROM traffic_metrics"))

    with op.batch_alter_table("traffic_metric_values") as batch:
        batch.alter_column(
            "assignment_id",
            existing_type=BIGINT,
            nullable=False,
        )

    with op.batch_alter_table("traffic_metric_assignments") as batch:
        batch.drop_column("include_legacy_values")


def downgrade() -> None:
    with op.batch_alter_table("traffic_metric_assignments") as batch:
        batch.add_column(
            sa.Column(
                "include_legacy_values",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            )
        )

    with op.batch_alter_table("traffic_metric_values") as batch:
        batch.alter_column(
            "assignment_id",
            existing_type=BIGINT,
            nullable=True,
        )
