from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProviderOutput(BaseModel):
    model_config = ConfigDict(extra="allow")


class LegacyScoreDimension(ProviderOutput):
    name: str = Field(min_length=1)
    score: int = Field(ge=0)
    full: int = Field(gt=0)
    comment: str | None = None


class ScoreDimension(ProviderOutput):
    label: str = Field(min_length=1)
    score: int = Field(ge=0)
    max: int = Field(gt=0)
    note: str | None = None


class DailyScoreProviderOutput(ProviderOutput):
    total_score: int = Field(ge=0, le=100)
    level: str = Field(min_length=1, max_length=50)
    score_delta: int | None = None
    trend_note: str | None = None
    one_line_review: str | None = None
    dimensions: dict[str, ScoreDimension] | list[LegacyScoreDimension]
    okr_outside_high_value: dict[str, Any] | list[str] = Field(default_factory=list)
    manager_hint: str | None = None
    memory_update: dict[str, Any] = Field(default_factory=dict)
    okr_clarity_warning: str | None = None

    @model_validator(mode="after")
    def validate_dimension_total(self) -> "DailyScoreProviderOutput":
        dimensions = self.dimensions.values() if isinstance(self.dimensions, dict) else self.dimensions
        values = list(dimensions)
        if not values:
            raise ValueError("dimensions must not be empty")
        if sum(item.score for item in values) != self.total_score:
            raise ValueError("total_score must equal the sum of dimension scores")
        if any(item.score > (item.max if isinstance(item, ScoreDimension) else item.full) for item in values):
            raise ValueError("dimension score cannot exceed its maximum")
        return self


class WeeklyDimension(ProviderOutput):
    score: int = Field(ge=0)
    full: int = Field(gt=0)
    note: str | None = None


class WeeklyScoreProviderOutput(ProviderOutput):
    total_score: int = Field(ge=0, le=100)
    level: str = Field(min_length=1, max_length=50)
    summary: str = Field(min_length=1)
    dimension_scores: dict[str, WeeklyDimension]
    key_achievements: list[str] = Field(default_factory=list)
    concerns: list[str] = Field(default_factory=list)
    manager_hint: str | None = None

    @model_validator(mode="after")
    def validate_dimensions(self) -> "WeeklyScoreProviderOutput":
        expected = {
            "产出与结果": 40,
            "问题方案质量": 30,
            "工作饱和度": 30,
        }
        if set(self.dimension_scores) != set(expected):
            raise ValueError("dimension_scores must contain the three required dimensions")
        if any(self.dimension_scores[name].full != full for name, full in expected.items()):
            raise ValueError("weekly dimension full scores must be 40, 30, and 30")
        if any(item.score > item.full for item in self.dimension_scores.values()):
            raise ValueError("dimension score cannot exceed its full score")
        if sum(item.score for item in self.dimension_scores.values()) != self.total_score:
            raise ValueError("total_score must equal the sum of dimension scores")
        return self


class SuggestionLinked(ProviderOutput):
    my_kr: str = ""
    others: str = ""


class SuggestionAsk(ProviderOutput):
    question: str = ""
    options: list[str] = Field(default_factory=list, max_length=3)


class SuggestionItem(ProviderOutput):
    type: Literal["red", "amber", "blue", "green"]
    title: str = Field(min_length=1, max_length=1000)
    reason: str = Field(min_length=1, max_length=2000)
    linked: SuggestionLinked = Field(default_factory=SuggestionLinked)
    needs_info: bool = False
    ask: SuggestionAsk = Field(default_factory=SuggestionAsk)

    @model_validator(mode="after")
    def validate_follow_up(self) -> "SuggestionItem":
        if self.needs_info:
            if not self.ask.question.strip():
                raise ValueError("needs_info suggestions must include an ask question")
            if not 2 <= len(self.ask.options) <= 3:
                raise ValueError("needs_info suggestions must include 2-3 quick options")
        return self


class DailySuggestionProviderOutput(ProviderOutput):
    summary: str = Field(min_length=1)
    suggestions: list[SuggestionItem] = Field(default_factory=list, max_length=5)


class OkrQualityDimension(ProviderOutput):
    score: int = Field(ge=0)
    full: int = Field(gt=0)
    note: str = Field(min_length=1)


class OkrOptionalImprovement(ProviderOutput):
    target: str = Field(min_length=1, max_length=500)
    point: str = Field(min_length=1, max_length=1000)
    suggestion: str = Field(min_length=1, max_length=2000)


class OkrReviewProviderOutput(ProviderOutput):
    total_score: int = Field(ge=0, le=100)
    level: str = Field(min_length=1, max_length=50)
    summary: str = Field(min_length=1)
    dimension_scores: dict[str, OkrQualityDimension]
    highlights: list[str] = Field(default_factory=list)
    optional_improvements: list[OkrOptionalImprovement] = Field(default_factory=list)
    impact_on_daily_scoring: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_dimensions(self) -> "OkrReviewProviderOutput":
        expected = {"O的价值": 40, "KR支撑度": 30, "工作饱和度": 30}
        if set(self.dimension_scores) != set(expected):
            raise ValueError("dimension_scores must contain the three required OKR dimensions")
        if any(self.dimension_scores[name].full != full for name, full in expected.items()):
            raise ValueError("OKR dimension full scores must be 40, 30, and 30")
        if any(item.score > item.full for item in self.dimension_scores.values()):
            raise ValueError("dimension score cannot exceed its full score")
        if sum(item.score for item in self.dimension_scores.values()) != self.total_score:
            raise ValueError("total_score must equal the sum of dimension scores")
        return self


class MonthlyReportDimension(ProviderOutput):
    score: int = Field(ge=0)
    full: int = Field(gt=0)
    note: str = Field(min_length=1)


class MonthlyReportScoreProviderOutput(ProviderOutput):
    total_score: int = Field(ge=0, le=100)
    summary: str = Field(min_length=1)
    dimension_scores: dict[str, MonthlyReportDimension]
    doubts: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list, min_length=2, max_length=3)

    @model_validator(mode="after")
    def validate_dimensions(self) -> "MonthlyReportScoreProviderOutput":
        expected = {
            "复盘与思考深度": 50,
            "工作饱和度": 20,
            "真实性与一致性": 15,
            "业绩与目标达成": 15,
        }
        if set(self.dimension_scores) != set(expected):
            raise ValueError("dimension_scores must contain the four monthly report dimensions")
        if any(self.dimension_scores[name].full != full for name, full in expected.items()):
            raise ValueError("monthly report dimension full scores must be 50, 20, 15, and 15")
        if any(item.score > item.full for item in self.dimension_scores.values()):
            raise ValueError("dimension score cannot exceed its full score")
        if sum(item.score for item in self.dimension_scores.values()) != self.total_score:
            raise ValueError("total_score must equal the sum of dimension scores")
        return self


OUTPUT_SCHEMAS: dict[str, type[ProviderOutput]] = {
    "daily_score": DailyScoreProviderOutput,
    "weekly_score": WeeklyScoreProviderOutput,
    "daily_suggestion": DailySuggestionProviderOutput,
    "okr_quality": OkrReviewProviderOutput,
    "monthly_report_score": MonthlyReportScoreProviderOutput,
}


def validate_provider_output(task_type: str, payload: object) -> dict:
    schema = OUTPUT_SCHEMAS.get(task_type)
    if schema is None:
        raise ValueError(f"Unsupported AI task type: {task_type}")
    if not isinstance(payload, dict):
        raise ValueError("AI output must be a JSON object")
    return schema.model_validate(payload).model_dump(mode="json")
