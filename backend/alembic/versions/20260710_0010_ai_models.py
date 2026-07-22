"""add AI provider config, prompt configs, tasks, daily scores/suggestions, okr reviews

Revision ID: 20260710_0010
Revises: 20260709_0009
Create Date: 2026-07-10 10:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_0010"
down_revision: str | None = "20260709_0009"
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
        "ai_provider_configs",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("provider", sa.String(length=30), nullable=False, server_default="openai_compatible"),
        sa.Column("api_base", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("default_model", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("extra_json", sa.Text(), nullable=True),
        *audit_columns(),
    )

    op.create_table(
        "ai_feature_flags",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("daily_score_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("daily_suggestion_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("okr_review_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("scheduler_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        *audit_columns(),
    )

    op.create_table(
        "prompt_configs",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("prompt_type", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False, server_default=""),
        sa.Column("template_content", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        *audit_columns(),
    )
    op.create_index("uq_prompt_configs_type", "prompt_configs", ["prompt_type"], unique=True)

    op.create_table(
        "ai_tasks",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, nullable=True),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("input_json", sa.Text(), nullable=True),
        sa.Column("output_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("prompt_config_id", BIGINT, nullable=True),
        sa.Column("ref_date", sa.Date(), nullable=True),
        sa.Column("ref_month", sa.String(length=7), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        *audit_columns(),
    )
    op.create_index("ix_ai_tasks_user_type", "ai_tasks", ["user_id", "task_type"])

    op.create_table(
        "daily_scores",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, nullable=False),
        sa.Column("score_date", sa.Date(), nullable=False),
        sa.Column("total_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("level", sa.String(length=50), nullable=True),
        sa.Column("score_delta", sa.Integer(), nullable=True),
        sa.Column("trend_note", sa.Text(), nullable=True),
        sa.Column("one_line_review", sa.Text(), nullable=True),
        sa.Column("dimensions_json", sa.Text(), nullable=True),
        sa.Column("okr_outside_high_value_json", sa.Text(), nullable=True),
        sa.Column("manager_hint", sa.Text(), nullable=True),
        sa.Column("okr_clarity_warning", sa.Text(), nullable=True),
        sa.Column("ai_task_id", BIGINT, nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        *audit_columns(),
    )
    op.create_index(
        "uq_daily_scores_user_date_active",
        "daily_scores",
        ["user_id", "score_date"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )

    op.create_table(
        "daily_suggestions",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, nullable=False),
        sa.Column("suggestion_date", sa.Date(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source_context_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("accepted_task_id", BIGINT, nullable=True),
        *audit_columns(),
    )
    op.create_index(
        "ix_daily_suggestions_user_date", "daily_suggestions", ["user_id", "suggestion_date"]
    )

    op.create_table(
        "okr_reviews",
        sa.Column("id", BIGINT, primary_key=True),
        sa.Column("user_id", BIGINT, nullable=False),
        sa.Column("month", sa.String(length=7), nullable=False),
        sa.Column("quality_score", sa.Numeric(5, 2), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("dimensions_json", sa.Text(), nullable=True),
        sa.Column("ai_task_id", BIGINT, nullable=True),
        sa.Column("generated_at", sa.DateTime(), nullable=True),
        *audit_columns(),
    )
    op.create_index(
        "uq_okr_reviews_user_month_active",
        "okr_reviews",
        ["user_id", "month"],
        unique=True,
        sqlite_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_okr_reviews_user_month_active", table_name="okr_reviews")
    op.drop_table("okr_reviews")
    op.drop_index("ix_daily_suggestions_user_date", table_name="daily_suggestions")
    op.drop_table("daily_suggestions")
    op.drop_index("uq_daily_scores_user_date_active", table_name="daily_scores")
    op.drop_table("daily_scores")
    op.drop_index("ix_ai_tasks_user_type", table_name="ai_tasks")
    op.drop_table("ai_tasks")
    op.drop_index("uq_prompt_configs_type", table_name="prompt_configs")
    op.drop_table("prompt_configs")
    op.drop_table("ai_feature_flags")
    op.drop_table("ai_provider_configs")
