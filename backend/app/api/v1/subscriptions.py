import re
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, require_permission
from app.core.permissions import FEATURE_DAILY, FEATURE_OKR
from app.db.session import get_db
from app.models.user import User
from app.schemas.subscription import (
    DailySubscriptionCandidateOut,
    DailySubscriptionOut,
    OkrSubscriptionCandidateOut,
    OkrSubscriptionOut,
    SubscribedDailyReportOut,
    SubscribedOkrMonthOut,
)
from app.services.subscription_service import SubscriptionService

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])


@router.get("/daily", response_model=list[DailySubscriptionOut])
def list_daily_subscriptions(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_DAILY)),
) -> list[DailySubscriptionOut]:
    return SubscriptionService(db, user).list_daily_subscriptions()


@router.get("/daily/candidates", response_model=list[DailySubscriptionCandidateOut])
def list_daily_candidates(
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_DAILY)),
) -> list[DailySubscriptionCandidateOut]:
    return SubscriptionService(db, user).list_daily_candidates(q)


@router.post(
    "/daily/{target_user_id}",
    response_model=DailySubscriptionOut,
    dependencies=[Depends(csrf_protect)],
)
def subscribe_daily(
    target_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_DAILY)),
) -> DailySubscriptionOut:
    return SubscriptionService(db, user).subscribe_daily(target_user_id)


@router.delete(
    "/daily/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(csrf_protect)],
)
def unsubscribe_daily(
    target_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_DAILY)),
) -> Response:
    SubscriptionService(db, user).unsubscribe_daily(target_user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/daily/{target_user_id}/report", response_model=SubscribedDailyReportOut)
def get_subscribed_daily_report(
    target_user_id: int,
    report_date: date = Query(alias="date"),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_DAILY)),
) -> SubscribedDailyReportOut:
    return SubscriptionService(db, user).get_daily_report(target_user_id, report_date)


# ---- OKR subscriptions -----------------------------------------------------

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _valid_month(month: str) -> str:
    if not _MONTH_RE.match(month):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="month must be YYYY-MM")
    return month


@router.get("/okr", response_model=list[OkrSubscriptionOut])
def list_okr_subscriptions(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_OKR)),
) -> list[OkrSubscriptionOut]:
    return SubscriptionService(db, user).list_okr_subscriptions()


@router.get("/okr/candidates", response_model=list[OkrSubscriptionCandidateOut])
def list_okr_candidates(
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_OKR)),
) -> list[OkrSubscriptionCandidateOut]:
    return SubscriptionService(db, user).list_okr_candidates(q)


@router.post(
    "/okr/{target_user_id}",
    response_model=OkrSubscriptionOut,
    dependencies=[Depends(csrf_protect)],
)
def subscribe_okr(
    target_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_OKR)),
) -> OkrSubscriptionOut:
    return SubscriptionService(db, user).subscribe_okr(target_user_id)


@router.delete(
    "/okr/{target_user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(csrf_protect)],
)
def unsubscribe_okr(
    target_user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_OKR)),
) -> Response:
    SubscriptionService(db, user).unsubscribe_okr(target_user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/okr/{target_user_id}/report", response_model=SubscribedOkrMonthOut)
def get_subscribed_okr_month(
    target_user_id: int,
    month: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_OKR)),
) -> SubscribedOkrMonthOut:
    return SubscriptionService(db, user).get_okr_month(target_user_id, _valid_month(month))
