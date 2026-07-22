from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Index, Integer, Numeric, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import AuditMixin, Base, TimestampMixin
from app.db.types import BigInt, JSONText


class AiProviderConfig(Base, TimestampMixin, AuditMixin):
    """Single-row global AI provider config (id=1), mirrors company_settings.

    The API key is stored encrypted (see utils/crypto) and never returned raw —
    the API layer masks it. ``enabled`` gates all AI generation; when off (or no
    key), features render a "not enabled" empty state instead of erroring.
    """

    __tablename__ = "ai_provider_configs"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    provider: Mapped[str] = mapped_column(String(30), default="openai_chat", nullable=False)
    api_base: Mapped[str] = mapped_column(String(300), default="", nullable=False)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_model: Mapped[str] = mapped_column(String(80), default="", nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    extra_json: Mapped[dict | None] = mapped_column(JSONText, nullable=True)


class AiFeatureFlags(Base, TimestampMixin, AuditMixin):
    """Single-row global feature toggles (id=1) for AI features + scheduling."""

    __tablename__ = "ai_feature_flags"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    daily_score_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    daily_suggestion_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    okr_review_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    scheduler_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)


class AiUserMemory(Base, TimestampMixin, AuditMixin):
    """Per-user long-term memory for the daily-score engine (one row per user).

    Accumulated across scorings via the model's ``memory_update`` block: recurring
    strengths/issues avoid repetitive praise/nagging, manager_hints accrue, and
    ``last_summary`` is the running profile. recent_scores are read live from
    daily_scores, not stored here.
    """

    __tablename__ = "ai_user_memory"
    __table_args__ = (
        Index(
            "uq_ai_user_memory_user_active",
            "user_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False, index=True)
    recurring_strengths_json: Mapped[list] = mapped_column(JSONText, default=list, nullable=False)
    recurring_issues_json: Mapped[list] = mapped_column(JSONText, default=list, nullable=False)
    manager_hints_json: Mapped[list] = mapped_column(JSONText, default=list, nullable=False)
    last_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class PromptConfig(Base, TimestampMixin, AuditMixin):
    """System-level prompt template, one row per prompt_type.

    Scope dimensions (organization/position/user) from the design doc are cut —
    positions were removed in v1.5 and the user confirmed a single system-level
    template per task type. ``restore-default`` overwrites from a code constant.
    """

    __tablename__ = "prompt_configs"
    __table_args__ = (Index("uq_prompt_configs_type", "prompt_type", unique=True),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    prompt_type: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), default="", nullable=False)
    template_content: Mapped[str] = mapped_column(Text, default="", nullable=False)
    version: Mapped[str] = mapped_column(String(50), default="v1", nullable=False)
    # Selected variable keys fed to the model as the 【数据】 block (see ai/defaults).
    variables_json: Mapped[list] = mapped_column(JSONText, default=list, nullable=False)


class AiTask(Base, TimestampMixin, AuditMixin):
    """Audit + status record for one AI generation call (design doc §7.8)."""

    __tablename__ = "ai_tasks"
    __table_args__ = (Index("ix_ai_tasks_user_type", "user_id", "task_type"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(BigInt, nullable=True)
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    input_json: Mapped[dict | list | None] = mapped_column(JSONText, nullable=True)
    output_json: Mapped[dict | list | None] = mapped_column(JSONText, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    model: Mapped[str | None] = mapped_column(String(80), nullable=True)
    prompt_config_id: Mapped[int | None] = mapped_column(BigInt, nullable=True)
    ref_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    ref_month: Mapped[str | None] = mapped_column(String(7), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DailyScore(Base, TimestampMixin, AuditMixin):
    """AI daily-report score (design doc §4.1.5 / §7.4)."""

    __tablename__ = "daily_scores"
    __table_args__ = (
        Index(
            "uq_daily_scores_user_date_active",
            "user_id",
            "score_date",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False)
    score_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    score_delta: Mapped[int | None] = mapped_column(Integer, nullable=True)
    trend_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    one_line_review: Mapped[str | None] = mapped_column(Text, nullable=True)
    dimensions_json: Mapped[dict | list | None] = mapped_column(JSONText, nullable=True)
    okr_outside_high_value_json: Mapped[dict | list | None] = mapped_column(JSONText, nullable=True)
    manager_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    okr_clarity_warning: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_task_id: Mapped[int | None] = mapped_column(BigInt, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class WeeklyScore(Base, TimestampMixin, AuditMixin):
    """AI score for one completed Monday-to-Sunday work week."""

    __tablename__ = "weekly_scores"
    __table_args__ = (
        Index(
            "uq_weekly_scores_user_week_active",
            "user_id",
            "week_start",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False)
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    dimensions_json: Mapped[dict | list | None] = mapped_column(JSONText, nullable=True)
    key_achievements_json: Mapped[list] = mapped_column(JSONText, default=list, nullable=False)
    concerns_json: Mapped[list] = mapped_column(JSONText, default=list, nullable=False)
    manager_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_task_id: Mapped[int | None] = mapped_column(BigInt, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class DailySuggestion(Base, TimestampMixin, AuditMixin):
    """AI "today's suggestion" item (design doc §4.1 / §7.4)."""

    __tablename__ = "daily_suggestions"
    __table_args__ = (Index("ix_daily_suggestions_user_date", "user_id", "suggestion_date"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False)
    suggestion_date: Mapped[date] = mapped_column(Date, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestion_type: Mapped[str] = mapped_column(String(10), default="amber", nullable=False)
    linked_json: Mapped[dict] = mapped_column(JSONText, default=dict, nullable=False)
    needs_info: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ask_json: Mapped[dict] = mapped_column(JSONText, default=dict, nullable=False)
    source_context_json: Mapped[dict | list | None] = mapped_column(JSONText, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    accepted_task_id: Mapped[int | None] = mapped_column(BigInt, nullable=True)


class OkrReview(Base, TimestampMixin, AuditMixin):
    """AI OKR monthly quality review (per user+month)."""

    __tablename__ = "okr_reviews"
    __table_args__ = (
        Index(
            "uq_okr_reviews_user_month_active",
            "user_id",
            "month",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    level: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    dimensions_json: Mapped[dict | list | None] = mapped_column(JSONText, nullable=True)
    highlights_json: Mapped[list] = mapped_column(JSONText, default=list, nullable=False)
    optional_improvements_json: Mapped[list] = mapped_column(JSONText, default=list, nullable=False)
    impact_on_daily_scoring: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_task_id: Mapped[int | None] = mapped_column(BigInt, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class MonthlyReportScore(Base, TimestampMixin, AuditMixin):
    """AI quality score for one employee's monthly report package."""

    __tablename__ = "monthly_report_scores"
    __table_args__ = (
        Index(
            "uq_monthly_report_scores_user_month_active",
            "user_id",
            "month",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInt, nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)
    total_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    dimensions_json: Mapped[dict | list | None] = mapped_column(JSONText, nullable=True)
    doubts_json: Mapped[list] = mapped_column(JSONText, default=list, nullable=False)
    suggestions_json: Mapped[list] = mapped_column(JSONText, default=list, nullable=False)
    ai_task_id: Mapped[int | None] = mapped_column(BigInt, nullable=True)
    generated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
