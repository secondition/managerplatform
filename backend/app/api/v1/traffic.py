from datetime import date

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.traffic import (
    TrafficMetricCreate,
    TrafficMetricOut,
    TrafficMetricUpdate,
    TrafficMetricValueUpdate,
    WeekColumnOut,
)
from app.services.traffic_service import DEFAULT_WEEK_COUNT, TrafficService

router = APIRouter(prefix="/traffic", tags=["traffic"])


@router.get("/weeks", response_model=list[WeekColumnOut])
def get_weeks(
    end: date | None = Query(default=None, description="Monday of the newest week; defaults to current week"),
    count: int = Query(default=DEFAULT_WEEK_COUNT, ge=1, le=52),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list:
    columns = TrafficService(db, user).resolve_window(end, count)
    return [
        {
            "week_index": c.week_index,
            "label": c.label,
            "week_start": c.week_start,
            "week_end": c.week_end,
            "is_empty": c.is_empty,
        }
        for c in columns
    ]


@router.get("/metrics", response_model=list[TrafficMetricOut])
def list_metrics(
    end: date | None = Query(default=None),
    count: int = Query(default=DEFAULT_WEEK_COUNT, ge=1, le=52),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return TrafficService(db, user).list_metrics(end, count)


@router.post("/metrics", response_model=list[TrafficMetricOut], dependencies=[Depends(csrf_protect)])
def create_metric(
    payload: TrafficMetricCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return TrafficService(db, user).create_metric(payload)


@router.patch(
    "/metrics/{metric_id}",
    response_model=list[TrafficMetricOut],
    dependencies=[Depends(csrf_protect)],
)
def update_metric(
    metric_id: int,
    payload: TrafficMetricUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    return TrafficService(db, user).update_metric(metric_id, payload)


@router.delete("/metrics/{metric_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(csrf_protect)])
def delete_metric(
    metric_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    TrafficService(db, user).delete_metric(metric_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/metric-assignments/{assignment_id}/values/{week_start}",
    response_model=TrafficMetricOut,
    dependencies=[Depends(csrf_protect)],
)
def upsert_metric_value(
    assignment_id: int,
    week_start: date,
    payload: TrafficMetricValueUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    return TrafficService(db, user).upsert_value(assignment_id, week_start, payload)
