"""create mvp backend tables

Revision ID: 20260706_0001
Revises:
Create Date: 2026-07-06 14:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260706_0001"
down_revision: str | None = None
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


def upgrade() -> None:
    op.create_table(
        "departments",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("parent_id", BIGINT, sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *audit_columns(),
    )

    op.create_table(
        "positions",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("department_id", BIGINT, sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *audit_columns(),
    )

    op.create_table(
        "users",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("email", sa.String(length=120), nullable=True),
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        sa.Column("role", sa.String(length=30), nullable=False, server_default="member"),
        sa.Column("feishu_union_id", sa.String(length=80), nullable=False),
        sa.Column("feishu_open_id", sa.String(length=80), nullable=False),
        sa.Column("feishu_user_id", sa.String(length=80), nullable=True),
        sa.Column("department_id", BIGINT, sa.ForeignKey("departments.id"), nullable=True),
        sa.Column("position_id", BIGINT, sa.ForeignKey("positions.id"), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_login_at", sa.DateTime(), nullable=True),
        *audit_columns(),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index(
        "uq_users_feishu_union_id_active",
        "users",
        ["feishu_union_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index(
        "uq_users_feishu_open_id_active",
        "users",
        ["feishu_open_id"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "user_permissions",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("permission", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        *audit_columns(),
    )
    op.create_index(
        "ix_user_permissions_user_permission",
        "user_permissions",
        ["user_id", "permission"],
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("user_agent", sa.String(length=300), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        *audit_columns(),
    )
    op.create_index("ix_refresh_tokens_token_hash", "refresh_tokens", ["token_hash"], unique=True)

    op.create_table(
        "daily_reports",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="draft"),
        *audit_columns(),
    )
    op.create_index(
        "uq_daily_reports_user_date_active",
        "daily_reports",
        ["user_id", "report_date"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "daily_tasks",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("report_id", BIGINT, sa.ForeignKey("daily_reports.id"), nullable=False),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("task_time", sa.Time(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("is_done", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("done_at", sa.DateTime(), nullable=True),
        sa.Column("repeat_rule", sa.String(length=50), nullable=False, server_default="none"),
        sa.Column("source", sa.String(length=50), nullable=False, server_default="manual"),
        sa.Column("assigned_to", BIGINT, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *audit_columns(),
    )
    op.create_index("ix_daily_tasks_report_sort", "daily_tasks", ["report_id", "sort_order"])

    op.create_table(
        "problem_solutions",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("report_id", BIGINT, sa.ForeignKey("daily_reports.id"), nullable=False),
        sa.Column("user_id", BIGINT, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("problem_text", sa.Text(), nullable=False),
        sa.Column("solution_html", sa.Text(), nullable=True),
        sa.Column("solution_json", sa.Text(), nullable=True),
        sa.Column("search_text", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        *audit_columns(),
    )
    op.create_index(
        "ix_problem_solutions_report_sort",
        "problem_solutions",
        ["report_id", "sort_order"],
    )

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


def downgrade() -> None:
    op.drop_table("traffic_metric_values")
    op.drop_index("ix_traffic_metrics_owner_month", table_name="traffic_metrics")
    op.drop_table("traffic_metrics")
    op.drop_index("ix_problem_solutions_report_sort", table_name="problem_solutions")
    op.drop_table("problem_solutions")
    op.drop_index("ix_daily_tasks_report_sort", table_name="daily_tasks")
    op.drop_table("daily_tasks")
    op.drop_index("uq_daily_reports_user_date_active", table_name="daily_reports")
    op.drop_table("daily_reports")
    op.drop_index("ix_refresh_tokens_token_hash", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_user_permissions_user_permission", table_name="user_permissions")
    op.drop_table("user_permissions")
    op.drop_index("uq_users_feishu_open_id_active", table_name="users")
    op.drop_index("uq_users_feishu_union_id_active", table_name="users")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.drop_table("positions")
    op.drop_table("departments")
