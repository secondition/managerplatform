"""Model -> schema serializers for AI outputs, shared by daily/okr/people APIs."""

from __future__ import annotations

from app.models.ai import (
    DailyScore,
    DailySuggestion,
    MonthlyReportScore,
    OkrReview,
    WeeklyScore,
)
from app.schemas.ai import (
    DailyScoreOut,
    DailySuggestionOut,
    MonthlyReportScoreOut,
    OkrImprovementOut,
    OkrReviewFullOut,
    ScoreDimension,
    WeeklyScoreOut,
)


def serialize_daily_score(row: DailyScore | None) -> DailyScoreOut:
    if row is None:
        return DailyScoreOut(status="empty")
    dims = [
        ScoreDimension(
            name=d.get("name", ""),
            score=int(d.get("score", 0)),
            full=int(d.get("full", 0)),
            comment=d.get("comment"),
        )
        for d in (row.dimensions_json or [])
    ]
    # okr_outside_high_value is stored as {ratio, items, manager_hint} (new) or a
    # bare list (legacy). Flatten to items + ratio for the API.
    okr_outside = row.okr_outside_high_value_json
    if isinstance(okr_outside, dict):
        okr_items = list(okr_outside.get("items") or [])
        okr_ratio = okr_outside.get("ratio") or ""
    else:
        okr_items = list(okr_outside or [])
        okr_ratio = ""
    return DailyScoreOut(
        status="ready",
        score_date=row.score_date,
        total_score=row.total_score,
        level=row.level,
        score_delta=row.score_delta,
        trend_note=row.trend_note,
        one_line_review=row.one_line_review,
        dimensions=dims,
        okr_outside_high_value=okr_items,
        okr_outside_ratio=okr_ratio,
        manager_hint=row.manager_hint,
        okr_clarity_warning=row.okr_clarity_warning,
        generated_at=row.generated_at,
    )


def serialize_weekly_score(row: WeeklyScore | None) -> WeeklyScoreOut:
    if row is None:
        return WeeklyScoreOut(status="empty")
    dimensions = [
        ScoreDimension(
            name=dimension.get("name", ""),
            score=int(dimension.get("score", 0)),
            full=int(dimension.get("full", 0)),
            comment=dimension.get("comment"),
        )
        for dimension in (row.dimensions_json or [])
    ]
    return WeeklyScoreOut(
        status="ready",
        week_start=row.week_start,
        week_end=row.week_end,
        total_score=row.total_score,
        level=row.level,
        summary=row.summary,
        dimensions=dimensions,
        key_achievements=list(row.key_achievements_json or []),
        concerns=list(row.concerns_json or []),
        manager_hint=row.manager_hint,
        generated_at=row.generated_at,
    )


def serialize_suggestion(row: DailySuggestion) -> DailySuggestionOut:
    return DailySuggestionOut(
        id=row.id,
        suggestion_date=row.suggestion_date,
        content=row.content,
        reason=row.reason,
        suggestion_type=row.suggestion_type,
        linked=dict(row.linked_json or {}),
        needs_info=row.needs_info,
        ask=dict(row.ask_json or {}),
        status=row.status,
        accepted_task_id=row.accepted_task_id,
    )


def serialize_okr_review(row: OkrReview | None) -> OkrReviewFullOut:
    if row is None or not row.level:
        return OkrReviewFullOut(status="empty")
    dimensions = [
        ScoreDimension(
            name=dimension.get("name", ""),
            score=int(dimension.get("score", 0)),
            full=int(dimension.get("full", 0)),
            comment=dimension.get("comment"),
        )
        for dimension in (row.dimensions_json or [])
    ]
    improvements = [
        OkrImprovementOut(
            target=item.get("target", ""),
            point=item.get("point", ""),
            suggestion=item.get("suggestion", ""),
        )
        for item in (row.optional_improvements_json or [])
    ]
    return OkrReviewFullOut(
        status="ready",
        month=row.month,
        total_score=row.quality_score,
        level=row.level,
        summary=row.summary,
        dimensions=dimensions,
        highlights=list(row.highlights_json or []),
        optional_improvements=improvements,
        impact_on_daily_scoring=row.impact_on_daily_scoring,
        generated_at=row.generated_at,
    )


def serialize_monthly_report_score(
    row: MonthlyReportScore | None,
) -> MonthlyReportScoreOut:
    if row is None:
        return MonthlyReportScoreOut(status="empty")
    dimensions = [
        ScoreDimension(
            name=dimension.get("name", ""),
            score=int(dimension.get("score", 0)),
            full=int(dimension.get("full", 0)),
            comment=dimension.get("comment"),
        )
        for dimension in (row.dimensions_json or [])
    ]
    return MonthlyReportScoreOut(
        status="ready",
        month=row.month,
        total_score=row.total_score,
        summary=row.summary,
        dimensions=dimensions,
        doubts=list(row.doubts_json or []),
        suggestions=list(row.suggestions_json or []),
        generated_at=row.generated_at,
    )
