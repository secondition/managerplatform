from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


# ---- provider config (admin) --------------------------------------------


class AiProviderOut(BaseModel):
    provider: str
    api_base: str
    default_model: str
    enabled: bool
    api_key_masked: str = ""
    api_key_set: bool = False


class AiProviderUpdate(BaseModel):
    provider: str | None = Field(default=None, max_length=30)
    api_base: str | None = Field(default=None, max_length=300)
    default_model: str | None = Field(default=None, max_length=80)
    enabled: bool | None = None
    # Send a new key to replace; omit/null keeps existing; empty string clears.
    api_key: str | None = None


class AiProviderTestOut(BaseModel):
    ok: bool
    message: str


# ---- feature flags (admin) ----------------------------------------------


class AiFeatureFlagsOut(ORMModel):
    daily_score_enabled: bool
    daily_suggestion_enabled: bool
    okr_review_enabled: bool
    scheduler_enabled: bool


class AiFeatureFlagsUpdate(BaseModel):
    daily_score_enabled: bool | None = None
    daily_suggestion_enabled: bool | None = None
    okr_review_enabled: bool | None = None
    scheduler_enabled: bool | None = None


# ---- prompt config (admin) ----------------------------------------------


class VariableInfo(BaseModel):
    key: str
    label: str
    description: str


class PromptConfigOut(ORMModel):
    id: int
    prompt_type: str
    name: str
    template_content: str
    version: str
    variables: list[str] = []
    available_variables: list[VariableInfo] = []


class PromptConfigUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    template_content: str | None = None
    version: str | None = Field(default=None, max_length=50)
    variables: list[str] | None = None


# ---- ai tasks -----------------------------------------------------------


class AiTaskOut(ORMModel):
    id: int
    user_id: int | None
    task_type: str
    status: str
    error_message: str | None
    model: str | None
    ref_date: date | None
    ref_month: str | None
    started_at: datetime | None
    finished_at: datetime | None


# ---- daily score --------------------------------------------------------


class ScoreDimension(BaseModel):
    name: str
    score: int
    full: int
    comment: str | None = None


class DailyScoreOut(BaseModel):
    status: str  # ready | empty | not_enabled
    score_date: date | None = None
    total_score: int | None = None
    level: str | None = None
    score_delta: int | None = None
    trend_note: str | None = None
    one_line_review: str | None = None
    dimensions: list[ScoreDimension] = []
    okr_outside_high_value: list[str] = []
    okr_outside_ratio: str = ""
    manager_hint: str | None = None
    okr_clarity_warning: str | None = None
    generated_at: datetime | None = None


# ---- weekly score -------------------------------------------------------


class WeeklyScoreOut(BaseModel):
    status: str  # ready | empty | not_enabled
    week_start: date | None = None
    week_end: date | None = None
    total_score: int | None = None
    level: str | None = None
    summary: str | None = None
    dimensions: list[ScoreDimension] = []
    key_achievements: list[str] = []
    concerns: list[str] = []
    manager_hint: str | None = None
    generated_at: datetime | None = None


# ---- daily suggestions --------------------------------------------------


class DailySuggestionOut(ORMModel):
    id: int
    suggestion_date: date
    content: str
    reason: str | None
    suggestion_type: str
    linked: dict[str, str] = {}
    needs_info: bool = False
    ask: dict = {}
    status: str
    accepted_task_id: int | None


class DailySuggestionListOut(BaseModel):
    status: str  # ready | empty | not_enabled
    summary: str = ""
    items: list[DailySuggestionOut] = []


class DailySuggestionGenerateIn(BaseModel):
    realtime_supplement: str = Field(default="", max_length=4000)


# ---- okr review ---------------------------------------------------------


class OkrImprovementOut(BaseModel):
    target: str
    point: str
    suggestion: str


class OkrReviewFullOut(BaseModel):
    status: str  # ready | empty | not_enabled
    month: str | None = None
    total_score: Decimal | None = None
    level: str | None = None
    summary: str | None = None
    dimensions: list[ScoreDimension] = []
    highlights: list[str] = []
    optional_improvements: list[OkrImprovementOut] = []
    impact_on_daily_scoring: str | None = None
    generated_at: datetime | None = None


# ---- monthly report score -----------------------------------------------


class MonthlyReportScoreOut(BaseModel):
    status: str  # ready | empty | not_enabled
    month: str | None = None
    total_score: int | None = None
    summary: str | None = None
    dimensions: list[ScoreDimension] = []
    doubts: list[str] = []
    suggestions: list[str] = []
    generated_at: datetime | None = None
