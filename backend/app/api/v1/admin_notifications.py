from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, require_permission
from app.core.config import settings
from app.core.permissions import ADMIN_NOTIFICATION
from app.db.session import get_db
from app.models.user import User
from app.schemas.notification import (
    FeishuTestIn,
    FeishuTestOut,
    NotificationChannelRuleOut,
    NotificationChannelRuleUpdate,
    NotificationDeliverySummaryOut,
)
from app.services.feishu_message_service import FeishuMessageClient, FeishuMessageError
from app.services.notification_service import NotificationService

router = APIRouter(prefix="/admin/notification-settings", tags=["admin-notifications"])


@router.get("", response_model=list[NotificationChannelRuleOut])
def list_notification_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_NOTIFICATION)),
) -> list[NotificationChannelRuleOut]:
    return [NotificationChannelRuleOut(**item) for item in NotificationService(db, user).list_rules()]


@router.patch(
    "/{notification_type}",
    response_model=NotificationChannelRuleOut,
    dependencies=[Depends(csrf_protect)],
)
def update_notification_setting(
    notification_type: str,
    payload: NotificationChannelRuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_NOTIFICATION)),
) -> NotificationChannelRuleOut:
    try:
        result = NotificationService(db, user).update_rule(
            notification_type,
            in_app_enabled=payload.in_app_enabled,
            feishu_enabled=payload.feishu_enabled,
        )
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown notification type") from exc
    return NotificationChannelRuleOut(**result)


@router.post("/test-feishu", response_model=FeishuTestOut, dependencies=[Depends(csrf_protect)])
def test_feishu(
    payload: FeishuTestIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_NOTIFICATION)),
) -> FeishuTestOut:
    if not settings.feishu_notification_enabled:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Feishu notifications are disabled")
    target = user if payload.user_id is None else db.scalar(
        select(User).where(
            User.id == payload.user_id,
            User.status == "active",
            User.deleted_at.is_(None),
        )
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not target.feishu_message_receive_id or not target.feishu_message_receive_id_type:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Feishu receiver is not synced")
    try:
        FeishuMessageClient().send_text(
            target.feishu_message_receive_id,
            target.feishu_message_receive_id_type,
            "通知测试\n企业管理工作台飞书通知配置正常。",
        )
    except FeishuMessageError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return FeishuTestOut(ok=True, message=f"测试消息已发送给 {target.name}")


@router.get("/delivery-summary", response_model=NotificationDeliverySummaryOut)
def delivery_summary(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_NOTIFICATION)),
) -> NotificationDeliverySummaryOut:
    return NotificationDeliverySummaryOut(**NotificationService(db, user).delivery_summary())
