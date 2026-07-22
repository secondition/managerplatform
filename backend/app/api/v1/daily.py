from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import (
    DailyScoreOut,
    DailySuggestionGenerateIn,
    DailySuggestionListOut,
    DailySuggestionOut,
    WeeklyScoreOut,
)
from app.schemas.daily import (
    DailyRangeDayOut,
    DailyReportOut,
    DailyTaskCreate,
    DailyTaskDoneIn,
    DailyTaskOut,
    DailyTaskUpdate,
    ProblemSolutionCreate,
    ProblemSolutionOut,
    ProblemSolutionUpdate,
    WeekDayOut,
)
from app.services.ai.provider import AiProviderError, AiProviderNotConfigured
from app.services.ai_serialize import (
    serialize_daily_score,
    serialize_suggestion,
    serialize_weekly_score,
)
from app.services.ai_service import AiService
from app.services.daily_service import DailyService

router = APIRouter(prefix="/daily", tags=["daily"])


@router.get("", response_model=DailyReportOut)
def get_daily(
    report_date: date = Query(alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DailyReportOut:
    return DailyService(db, user).get_own_daily_out(report_date)


@router.get("/range", response_model=list[DailyRangeDayOut])
def get_daily_range(
    start_date: date = Query(alias="start"),
    end_date: date = Query(alias="end"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[DailyRangeDayOut]:
    if end_date < start_date:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="end must be on or after start",
        )
    if (end_date - start_date).days > 41:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date range cannot exceed 42 days",
        )
    return DailyService(db, user).get_own_range_out(start_date, end_date)


@router.get("/week", response_model=list[WeekDayOut])
def get_week(
    report_date: date = Query(alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return DailyService(db, user).week_summary(report_date)


@router.post("/tasks", response_model=DailyTaskOut, dependencies=[Depends(csrf_protect)])
def create_task(
    payload: DailyTaskCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DailyTaskOut:
    service = DailyService(db, user)
    return service.serialize_task(service.create_task(payload))


@router.patch("/tasks/{task_id}", response_model=DailyTaskOut, dependencies=[Depends(csrf_protect)])
def update_task(
    task_id: int,
    payload: DailyTaskUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DailyTaskOut:
    service = DailyService(db, user)
    return service.serialize_task(service.update_task(task_id, payload))


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(csrf_protect)])
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    DailyService(db, user).delete_task(task_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/tasks/{task_id}/done", response_model=DailyTaskOut, dependencies=[Depends(csrf_protect)])
def set_task_done(
    task_id: int,
    payload: DailyTaskDoneIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DailyTaskOut:
    service = DailyService(db, user)
    return service.serialize_task(service.set_task_done(task_id, payload))


@router.post("/problems", response_model=ProblemSolutionOut, dependencies=[Depends(csrf_protect)])
def create_problem(
    payload: ProblemSolutionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProblemSolutionOut:
    return DailyService(db, user).create_problem(payload)


@router.patch("/problems/{problem_id}", response_model=ProblemSolutionOut, dependencies=[Depends(csrf_protect)])
def update_problem(
    problem_id: int,
    payload: ProblemSolutionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ProblemSolutionOut:
    return DailyService(db, user).update_problem(problem_id, payload)


@router.delete("/problems/{problem_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(csrf_protect)])
def delete_problem(
    problem_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    DailyService(db, user).delete_problem(problem_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- AI: daily score + today's suggestions -------------------------------


@router.get("/scores", response_model=DailyScoreOut)
def get_daily_score(
    report_date: date = Query(alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DailyScoreOut:
    row = AiService(db, user).get_daily_score(report_date)
    return serialize_daily_score(row)


@router.post("/scores/generate", response_model=DailyScoreOut, dependencies=[Depends(csrf_protect)])
def generate_daily_score(
    report_date: date = Query(alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DailyScoreOut:
    service = AiService(db, user)
    if not service.get_flags().daily_score_enabled:
        return DailyScoreOut(status="not_enabled")
    try:
        row = service.generate_daily_score(report_date)
    except AiProviderNotConfigured:
        return DailyScoreOut(status="not_enabled")
    except AiProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return serialize_daily_score(row)


@router.get("/weekly-score", response_model=WeeklyScoreOut)
def get_weekly_score(
    anchor_date: date = Query(alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WeeklyScoreOut:
    return serialize_weekly_score(AiService(db, user).get_weekly_score(anchor_date))


@router.post(
    "/weekly-score/generate",
    response_model=WeeklyScoreOut,
    dependencies=[Depends(csrf_protect)],
)
def generate_weekly_score(
    anchor_date: date = Query(alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> WeeklyScoreOut:
    service = AiService(db, user)
    if not service.get_flags().daily_score_enabled:
        return WeeklyScoreOut(status="not_enabled")
    try:
        row = service.generate_weekly_score(anchor_date)
    except AiProviderNotConfigured:
        return WeeklyScoreOut(status="not_enabled")
    except AiProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return serialize_weekly_score(row)


@router.get("/suggestions", response_model=DailySuggestionListOut)
def get_suggestions(
    suggestion_date: date = Query(alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DailySuggestionListOut:
    service = AiService(db, user)
    items = service.list_suggestions(suggestion_date)
    return DailySuggestionListOut(
        status="ready" if items else "empty",
        summary=service.latest_suggestion_summary(suggestion_date),
        items=[serialize_suggestion(row) for row in items],
    )


@router.post(
    "/suggestions/generate",
    response_model=DailySuggestionListOut,
    dependencies=[Depends(csrf_protect)],
)
def generate_suggestions(
    suggestion_date: date = Query(alias="date"),
    payload: DailySuggestionGenerateIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DailySuggestionListOut:
    service = AiService(db, user)
    if not service.get_flags().daily_suggestion_enabled:
        return DailySuggestionListOut(status="not_enabled")
    try:
        items = service.generate_suggestions(
            suggestion_date,
            realtime_supplement=payload.realtime_supplement if payload else "",
        )
    except AiProviderNotConfigured:
        return DailySuggestionListOut(status="not_enabled")
    except AiProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return DailySuggestionListOut(
        status="ready" if items else "empty",
        summary=service.latest_suggestion_summary(suggestion_date),
        items=[serialize_suggestion(row) for row in items],
    )


@router.post(
    "/suggestions/{suggestion_id}/accept",
    response_model=DailySuggestionOut,
    dependencies=[Depends(csrf_protect)],
)
def accept_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DailySuggestionOut:
    service = AiService(db, user)
    row = service.get_suggestion(suggestion_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")
    try:
        return serialize_suggestion(service.accept_suggestion(row))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/suggestions/{suggestion_id}/reject",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(csrf_protect)],
)
def reject_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    service = AiService(db, user)
    row = service.get_suggestion(suggestion_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Suggestion not found")
    try:
        service.reject_suggestion(row)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
