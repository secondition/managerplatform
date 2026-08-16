from datetime import datetime

from pydantic import BaseModel, Field


class NotificationOut(BaseModel):
    id: int
    type: str
    title: str
    body: str
    action_url: str | None
    entity_type: str | None
    entity_id: int | None
    metadata: dict | list | None
    read_at: datetime | None
    created_at: datetime


class NotificationPageOut(BaseModel):
    items: list[NotificationOut]
    next_cursor: int | None


class NotificationUnreadCountOut(BaseModel):
    count: int


class NotificationChannelRuleUpdate(BaseModel):
    in_app_enabled: bool | None = None
    feishu_enabled: bool | None = None


class NotificationChannelRuleOut(BaseModel):
    notification_type: str
    label: str
    description: str
    in_app_enabled: bool
    feishu_enabled: bool
    feishu_available: bool


class FeishuTestIn(BaseModel):
    user_id: int | None = None


class FeishuTestOut(BaseModel):
    ok: bool
    message: str


class NotificationDeliverySummaryOut(BaseModel):
    pending: int = 0
    retry: int = 0
    sent: int = 0
    failed: int = 0
    cancelled: int = 0
    latest_errors: list[str] = Field(default_factory=list)
