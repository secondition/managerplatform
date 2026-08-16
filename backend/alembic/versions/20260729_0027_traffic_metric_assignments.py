"""split traffic metrics into independent assignee instances

Revision ID: 20260729_0027
Revises: 20260720_0026
"""

from collections.abc import Sequence
from datetime import date, timedelta

import sqlalchemy as sa
from alembic import op

revision: str = "20260729_0027"
down_revision: str | None = "20260720_0026"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BIGINT = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def _current_week_start() -> date:
    today = date.today()
    return today - timedelta(days=today.weekday())


def upgrade() -> None:
    op.create_table(
        "traffic_metric_assignments",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("metric_id", BIGINT, sa.ForeignKey("traffic_metrics.id"), nullable=False),
        sa.Column("assignee_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_by_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "include_legacy_values",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
        sa.UniqueConstraint("metric_id", "assignee_id", name="uq_metric_assignee"),
    )
    op.create_index(
        "ix_traffic_metric_assignments_assignee",
        "traffic_metric_assignments",
        ["assignee_id"],
    )

    cutoff = _current_week_start()
    connection = op.get_bind()
    traffic_metrics = sa.table(
        "traffic_metrics",
        sa.column("id", BIGINT),
        sa.column("owner_id", BIGINT),
    )
    traffic_members = sa.table(
        "traffic_metric_members",
        sa.column("metric_id", BIGINT),
        sa.column("user_id", BIGINT),
        sa.column("role", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
        sa.column("deleted_at", sa.DateTime()),
        sa.column("created_by", BIGINT),
        sa.column("updated_by", BIGINT),
    )
    assignments = sa.table(
        "traffic_metric_assignments",
        sa.column("metric_id", BIGINT),
        sa.column("assignee_id", BIGINT),
        sa.column("assigned_by_id", BIGINT),
        sa.column("effective_from", sa.Date()),
        sa.column("include_legacy_values", sa.Boolean()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
        sa.column("deleted_at", sa.DateTime()),
        sa.column("created_by", BIGINT),
        sa.column("updated_by", BIGINT),
    )
    editor_rows = connection.execute(
        sa.select(
            traffic_members.c.metric_id,
            traffic_members.c.user_id,
            traffic_members.c.created_at,
            traffic_members.c.updated_at,
            traffic_members.c.deleted_at,
            traffic_members.c.created_by,
            traffic_members.c.updated_by,
            traffic_metrics.c.owner_id,
        )
        .select_from(
            traffic_members.join(
                traffic_metrics,
                traffic_metrics.c.id == traffic_members.c.metric_id,
            )
        )
        .where(traffic_members.c.role == "editor")
    ).all()
    for row in editor_rows:
        connection.execute(
            assignments.insert().values(
                metric_id=row.metric_id,
                assignee_id=row.user_id,
                assigned_by_id=row.owner_id,
                effective_from=cutoff,
                include_legacy_values=row.deleted_at is None,
                created_at=row.created_at,
                updated_at=row.updated_at,
                deleted_at=row.deleted_at,
                created_by=row.created_by or row.owner_id,
                updated_by=row.updated_by or row.owner_id,
            )
        )
    connection.execute(
        traffic_members.update()
        .where(traffic_members.c.role == "editor", traffic_members.c.deleted_at.is_(None))
        .values(deleted_at=sa.func.current_timestamp())
    )

    with op.batch_alter_table("traffic_metric_values") as batch:
        batch.drop_constraint("uq_metric_week", type_="unique")
        batch.add_column(sa.Column("assignment_id", BIGINT, nullable=True))
        batch.create_foreign_key(
            "fk_traffic_metric_values_assignment_id_traffic_metric_assignments",
            "traffic_metric_assignments",
            ["assignment_id"],
            ["id"],
        )
        batch.create_unique_constraint(
            "uq_metric_assignment_week",
            ["assignment_id", "week_start"],
        )
        batch.create_index(
            "ix_traffic_metric_values_metric_week",
            ["metric_id", "week_start"],
        )


def downgrade() -> None:
    connection = op.get_bind()
    assignments = sa.table(
        "traffic_metric_assignments",
        sa.column("metric_id", BIGINT),
        sa.column("assignee_id", BIGINT),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
        sa.column("deleted_at", sa.DateTime()),
        sa.column("created_by", BIGINT),
        sa.column("updated_by", BIGINT),
    )
    traffic_members = sa.table(
        "traffic_metric_members",
        sa.column("metric_id", BIGINT),
        sa.column("user_id", BIGINT),
        sa.column("role", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
        sa.column("deleted_at", sa.DateTime()),
        sa.column("created_by", BIGINT),
        sa.column("updated_by", BIGINT),
    )
    for assignment in connection.execute(sa.select(assignments)).all():
        member = connection.execute(
            sa.select(traffic_members.c.metric_id).where(
                traffic_members.c.metric_id == assignment.metric_id,
                traffic_members.c.user_id == assignment.assignee_id,
            )
        ).first()
        member_values = {
            "role": "editor",
            "updated_at": assignment.updated_at,
            "deleted_at": assignment.deleted_at,
            "updated_by": assignment.updated_by,
        }
        if member is None:
            connection.execute(
                traffic_members.insert().values(
                    metric_id=assignment.metric_id,
                    user_id=assignment.assignee_id,
                    created_at=assignment.created_at,
                    created_by=assignment.created_by,
                    **member_values,
                )
            )
        else:
            connection.execute(
                traffic_members.update()
                .where(
                    traffic_members.c.metric_id == assignment.metric_id,
                    traffic_members.c.user_id == assignment.assignee_id,
                )
                .values(**member_values)
            )

    values = sa.table(
        "traffic_metric_values",
        sa.column("assignment_id", BIGINT),
    )
    connection.execute(values.delete().where(values.c.assignment_id.is_not(None)))

    with op.batch_alter_table("traffic_metric_values") as batch:
        batch.drop_index("ix_traffic_metric_values_metric_week")
        batch.drop_constraint("uq_metric_assignment_week", type_="unique")
        batch.drop_constraint(
            "fk_traffic_metric_values_assignment_id_traffic_metric_assignments",
            type_="foreignkey",
        )
        batch.drop_column("assignment_id")
        batch.create_unique_constraint("uq_metric_week", ["metric_id", "week_start"])

    op.drop_index(
        "ix_traffic_metric_assignments_assignee",
        table_name="traffic_metric_assignments",
    )
    op.drop_table("traffic_metric_assignments")
