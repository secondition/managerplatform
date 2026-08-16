from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, get_current_user
from app.core.security import utcnow
from app.db.session import get_db
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import NotificationOut, NotificationPageOut, NotificationUnreadCountOut
from app.services.notification_service import serialize_notification

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationPageOut)
def list_notifications(
    unread_only: bool = False,
    cursor: int | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationPageOut:
    conditions = [
        Notification.recipient_id == user.id,
        Notification.in_app_visible.is_(True),
        Notification.deleted_at.is_(None),
    ]
    if unread_only:
        conditions.append(Notification.read_at.is_(None))
    if cursor is not None:
        conditions.append(Notification.id < cursor)
    rows = list(
        db.scalars(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.id.desc())
            .limit(limit + 1)
        ).all()
    )
    has_more = len(rows) > limit
    rows = rows[:limit]
    return NotificationPageOut(
        items=[NotificationOut(**serialize_notification(row)) for row in rows],
        next_cursor=rows[-1].id if has_more and rows else None,
    )


@router.get("/unread-count", response_model=NotificationUnreadCountOut)
def unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationUnreadCountOut:
    count = db.scalar(
        select(func.count(Notification.id)).where(
            Notification.recipient_id == user.id,
            Notification.in_app_visible.is_(True),
            Notification.read_at.is_(None),
            Notification.deleted_at.is_(None),
        )
    )
    return NotificationUnreadCountOut(count=int(count or 0))


@router.post("/{notification_id}/read", response_model=NotificationOut, dependencies=[Depends(csrf_protect)])
def mark_read(
    notification_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationOut:
    row = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.recipient_id == user.id,
            Notification.in_app_visible.is_(True),
            Notification.deleted_at.is_(None),
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if row.read_at is None:
        row.read_at = utcnow()
        row.updated_by = user.id
        db.commit()
        db.refresh(row)
    return NotificationOut(**serialize_notification(row))


@router.post("/read-all", response_model=NotificationUnreadCountOut, dependencies=[Depends(csrf_protect)])
def mark_all_read(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> NotificationUnreadCountOut:
    rows = db.scalars(
        select(Notification).where(
            Notification.recipient_id == user.id,
            Notification.in_app_visible.is_(True),
            Notification.read_at.is_(None),
            Notification.deleted_at.is_(None),
        )
    ).all()
    now = utcnow()
    for row in rows:
        row.read_at = now
        row.updated_by = user.id
    db.commit()
    return NotificationUnreadCountOut(count=0)
