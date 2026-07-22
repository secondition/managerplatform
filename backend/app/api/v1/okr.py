import re

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import MonthlyReportScoreOut, OkrReviewFullOut
from app.schemas.okr import (
    KeyResultCreate,
    KeyResultProgressCreate,
    KeyResultProgressOut,
    KeyResultUpdate,
    MonthlyReportSectionOut,
    MonthlyReportSectionUpdate,
    ObjectiveCreate,
    ObjectiveOut,
    ObjectiveUpdate,
    OkrOrderUpdate,
    OkrCommentCreate,
    OkrCommentOut,
    OkrCommentUpdate,
    OkrMonthOut,
)
from app.services.ai.provider import AiProviderError, AiProviderNotConfigured
from app.services.ai_serialize import serialize_monthly_report_score, serialize_okr_review
from app.services.ai_service import AiService
from app.services.okr_service import OkrService

router = APIRouter(prefix="/okr", tags=["okr"])

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _valid_month(month: str) -> str:
    if not _MONTH_RE.match(month):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="month must be YYYY-MM")
    return month


@router.get("", response_model=OkrMonthOut)
def get_month(
    month: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return OkrService(db, user).get_month(_valid_month(month))


@router.post("/objectives", response_model=ObjectiveOut, dependencies=[Depends(csrf_protect)])
def create_objective(
    payload: ObjectiveCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return OkrService(db, user).create_objective(payload)


@router.patch("/objectives/{objective_id}", response_model=ObjectiveOut, dependencies=[Depends(csrf_protect)])
def update_objective(
    objective_id: int,
    payload: ObjectiveUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return OkrService(db, user).update_objective(objective_id, payload)


@router.post("/objectives/reorder", response_model=OkrMonthOut, dependencies=[Depends(csrf_protect)])
def reorder_objectives(
    payload: OkrOrderUpdate,
    month: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return OkrService(db, user).reorder_objectives(_valid_month(month), payload.ids)


@router.delete(
    "/objectives/{objective_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(csrf_protect)],
)
def delete_objective(
    objective_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    OkrService(db, user).delete_objective(objective_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/objectives/{objective_id}/key-results",
    response_model=ObjectiveOut,
    dependencies=[Depends(csrf_protect)],
)
def add_key_result(
    objective_id: int,
    payload: KeyResultCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return OkrService(db, user).add_key_result(objective_id, payload)


@router.patch("/key-results/{kr_id}", response_model=ObjectiveOut, dependencies=[Depends(csrf_protect)])
def update_key_result(
    kr_id: int,
    payload: KeyResultUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return OkrService(db, user).update_key_result(kr_id, payload)


@router.post("/objectives/{objective_id}/key-results/reorder", response_model=ObjectiveOut, dependencies=[Depends(csrf_protect)])
def reorder_key_results(
    objective_id: int,
    payload: OkrOrderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return OkrService(db, user).reorder_key_results(objective_id, payload.ids)


@router.delete("/key-results/{kr_id}", response_model=ObjectiveOut, dependencies=[Depends(csrf_protect)])
def delete_key_result(
    kr_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return OkrService(db, user).delete_key_result(kr_id)


@router.get("/key-results/{kr_id}/progress", response_model=list[KeyResultProgressOut])
def list_key_result_progress(
    kr_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list:
    return OkrService(db, user).list_key_result_progress(kr_id)


@router.post(
    "/key-results/{kr_id}/progress",
    response_model=KeyResultProgressOut,
    dependencies=[Depends(csrf_protect)],
)
def create_key_result_progress(
    kr_id: int,
    payload: KeyResultProgressCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return OkrService(db, user).create_key_result_progress(kr_id, payload)


@router.get("/objectives/{objective_id}/comments", response_model=list[OkrCommentOut])
def list_objective_comments(
    objective_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return OkrService(db, user).list_objective_comments(objective_id)


@router.post(
    "/objectives/{objective_id}/comments",
    response_model=OkrCommentOut,
    dependencies=[Depends(csrf_protect)],
)
def create_objective_comment(
    objective_id: int,
    payload: OkrCommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return OkrService(db, user).create_objective_comment(objective_id, payload)


@router.get("/key-results/{kr_id}/comments", response_model=list[OkrCommentOut])
def list_key_result_comments(
    kr_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return OkrService(db, user).list_key_result_comments(kr_id)


@router.post(
    "/key-results/{kr_id}/comments",
    response_model=OkrCommentOut,
    dependencies=[Depends(csrf_protect)],
)
def create_key_result_comment(
    kr_id: int,
    payload: OkrCommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return OkrService(db, user).create_key_result_comment(kr_id, payload)


@router.patch(
    "/comments/{comment_id}",
    response_model=OkrCommentOut,
    dependencies=[Depends(csrf_protect)],
)
def update_comment(
    comment_id: int,
    payload: OkrCommentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return OkrService(db, user).update_comment(comment_id, payload)


@router.delete(
    "/comments/{comment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(csrf_protect)],
)
def delete_comment(
    comment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    OkrService(db, user).delete_comment(comment_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/review", response_model=OkrReviewFullOut)
def get_review(
    month: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkrReviewFullOut:
    _valid_month(month)
    return serialize_okr_review(AiService(db, user).get_okr_review(month))


@router.post("/review/generate", response_model=OkrReviewFullOut, dependencies=[Depends(csrf_protect)])
def generate_review(
    month: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> OkrReviewFullOut:
    _valid_month(month)
    service = AiService(db, user)
    if not service.get_flags().okr_review_enabled:
        return OkrReviewFullOut(status="not_enabled")
    try:
        row = service.generate_okr_review(month)
    except AiProviderNotConfigured:
        return OkrReviewFullOut(status="not_enabled")
    except AiProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return serialize_okr_review(row)


@router.get("/monthly-report/score", response_model=MonthlyReportScoreOut)
def get_monthly_report_score(
    month: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MonthlyReportScoreOut:
    _valid_month(month)
    return serialize_monthly_report_score(
        AiService(db, user).get_monthly_report_score(month)
    )


@router.post(
    "/monthly-report/score/generate",
    response_model=MonthlyReportScoreOut,
    dependencies=[Depends(csrf_protect)],
)
def generate_monthly_report_score(
    month: str = Query(..., description="YYYY-MM"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MonthlyReportScoreOut:
    _valid_month(month)
    service = AiService(db, user)
    if not service.get_flags().okr_review_enabled:
        return MonthlyReportScoreOut(status="not_enabled")
    try:
        row = service.generate_monthly_report_score(month)
    except AiProviderNotConfigured:
        return MonthlyReportScoreOut(status="not_enabled")
    except AiProviderError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    return serialize_monthly_report_score(row)


@router.patch(
    "/monthly-report/sections/{section_id}",
    response_model=MonthlyReportSectionOut,
    dependencies=[Depends(csrf_protect)],
)
def update_report_section(
    section_id: int,
    payload: MonthlyReportSectionUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return OkrService(db, user).update_section(section_id, payload)
