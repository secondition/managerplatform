"""rework traffic metrics into long-lived weekly-target model

Drops the month-scoped traffic tables and recreates them around a single
weekly target with ISO-week-keyed values. Old traffic data is discarded
(agreed for MVP).

Revision ID: 20260709_0006
Revises: 20260709_0005
Create Date: 2026-07-09 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260709_0006"
down_revision: str | None = "20260709_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

BIGINT = sa.BigInteger().with_variant(sa.Integer, "sqlite")


def audit_columns() -> list[sa.Column]:
    return [
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", BIGINT, nullable=True),
        sa.Column("updated_by", BIGINT, nullable=True),
    ]


def _create_metrics() -> None:
    op.create_table(
        "traffic_metrics",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("owner_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("weekly_target", sa.Numeric(18, 4), nullable=True),
        sa.Column("range_min", sa.Numeric(18, 4), nullable=True),
        sa.Column("range_max", sa.Numeric(18, 4), nullable=True),
        sa.Column("is_north_star", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *audit_columns(),
    )
    op.create_index("ix_traffic_metrics_owner", "traffic_metrics", ["owner_id"])

    op.create_table(
        "traffic_metric_values",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("metric_id", BIGINT, sa.ForeignKey("traffic_metrics.id"), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("week_end", sa.Date(), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="missed"),
        sa.Column("note", sa.Text(), nullable=True),
        *audit_columns(),
        sa.UniqueConstraint("metric_id", "week_start", name="uq_metric_week"),
    )

    op.create_table(
        "traffic_metric_members",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("metric_id", BIGINT, sa.ForeignKey("traffic_metrics.id"), nullable=False),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"),
        *audit_columns(),
        sa.UniqueConstraint("metric_id", "user_id", name="uq_metric_member"),
    )


def _create_legacy() -> None:
    op.create_table(
        "traffic_metrics",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("owner_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=True),
        sa.Column("unit", sa.String(length=30), nullable=True),
        sa.Column("start_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("target_value", sa.Numeric(18, 4), nullable=False),
        sa.Column("direction", sa.String(length=20), nullable=False),
        sa.Column("range_min", sa.Numeric(18, 4), nullable=True),
        sa.Column("range_max", sa.Numeric(18, 4), nullable=True),
        sa.Column("is_north_star", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("agg_mode", sa.String(length=20), nullable=False, server_default="latest"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *audit_columns(),
    )
    op.create_index("ix_traffic_metrics_owner_month", "traffic_metrics", ["owner_id", "month"])

    op.create_table(
        "traffic_metric_values",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("metric_id", BIGINT, sa.ForeignKey("traffic_metrics.id"), nullable=False),
        sa.Column("week_index", sa.Integer(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=True),
        sa.Column("week_end", sa.Date(), nullable=True),
        sa.Column("value", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="no_progress"),
        sa.Column("note", sa.Text(), nullable=True),
        *audit_columns(),
        sa.UniqueConstraint("metric_id", "week_index", name="uq_metric_week"),
    )

    op.create_table(
        "traffic_metric_members",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("metric_id", BIGINT, sa.ForeignKey("traffic_metrics.id"), nullable=False),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False, server_default="viewer"),
        *audit_columns(),
        sa.UniqueConstraint("metric_id", "user_id", name="uq_metric_member"),
    )


def _drop_all() -> None:
    op.drop_table("traffic_metric_members")
    op.drop_table("traffic_metric_values")
    try:
        op.drop_index("ix_traffic_metrics_owner", table_name="traffic_metrics")
    except Exception:  # noqa: BLE001 - index name differs across schema versions
        pass
    try:
        op.drop_index("ix_traffic_metrics_owner_month", table_name="traffic_metrics")
    except Exception:  # noqa: BLE001
        pass
    op.drop_table("traffic_metrics")


def upgrade() -> None:
    _drop_all()
    _create_metrics()


def downgrade() -> None:
    _drop_all()
    _create_legacy()
