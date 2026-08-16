from __future__ import annotations

import json
from datetime import timedelta

import httpx
from sqlalchemy import or_, select

from app.core.config import settings
from app.core.security import utcnow
from app.db.session import SessionLocal
from app.models.notification import Notification, NotificationDelivery


class FeishuMessageError(RuntimeError):
    pass


def _request_error(operation: str, exc: httpx.RequestError) -> FeishuMessageError:
    detail = str(exc).strip() or exc.__class__.__name__
    return FeishuMessageError(f"{operation} ({exc.__class__.__name__}): {detail}")


def _response_payload(response: httpx.Response, operation: str) -> dict:
    try:
        payload = response.json()
    except ValueError as exc:
        excerpt = " ".join(response.text.split())[:500] or "<empty response>"
        raise FeishuMessageError(
            f"{operation} returned invalid JSON (HTTP {response.status_code}): {excerpt}"
        ) from exc
    if not isinstance(payload, dict):
        raise FeishuMessageError(
            f"{operation} returned an unexpected response (HTTP {response.status_code})"
        )
    return payload


def _raise_for_feishu_error(
    response: httpx.Response,
    payload: dict,
    operation: str,
) -> None:
    code = payload.get("code")
    if response.is_success and code in (None, 0):
        return

    context = [f"HTTP {response.status_code}"]
    if code is not None:
        context.append(f"code {code}")
    error = payload.get("error")
    error_details = error if isinstance(error, dict) else {}
    log_id = (
        error_details.get("log_id")
        or payload.get("request_id")
        or response.headers.get("x-tt-logid")
    )
    if log_id:
        context.append(f"log_id {log_id}")

    message = payload.get("msg") or payload.get("message") or "Feishu rejected the request"
    detail = f"{operation} ({', '.join(context)}): {message}"
    troubleshooter = error_details.get("troubleshooter")
    if troubleshooter:
        detail += f"; troubleshooter: {troubleshooter}"
    raise FeishuMessageError(detail)


class FeishuMessageClient:
    def __init__(self) -> None:
        self._tenant_token: str | None = None
        self._tenant_token_expires_at = utcnow()

    def tenant_access_token(self) -> str:
        if self._tenant_token and utcnow() < self._tenant_token_expires_at:
            return self._tenant_token
        try:
            response = httpx.post(
                f"{settings.feishu_api_base}{settings.feishu_tenant_token_path}",
                json={"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret},
                timeout=10.0,
            )
        except httpx.RequestError as exc:
            raise _request_error("飞书租户令牌请求失败", exc) from exc
        payload = _response_payload(response, "飞书租户令牌请求失败")
        _raise_for_feishu_error(response, payload, "飞书租户令牌请求失败")
        token = payload.get("tenant_access_token")
        if not token:
            raise FeishuMessageError("Feishu tenant token response is missing tenant_access_token")
        expires_in = int(payload.get("expire") or 7200)
        self._tenant_token = str(token)
        self._tenant_token_expires_at = utcnow() + timedelta(seconds=max(60, expires_in - 60))
        return self._tenant_token

    def send_text(self, receive_id: str, receive_id_type: str, text: str) -> None:
        if receive_id_type not in {"open_id", "user_id", "union_id", "email", "chat_id"}:
            raise FeishuMessageError(f"Unsupported Feishu receive_id_type: {receive_id_type}")
        token = self.tenant_access_token()
        try:
            response = httpx.post(
                f"{settings.feishu_api_base}/open-apis/im/v1/messages",
                params={"receive_id_type": receive_id_type},
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "receive_id": receive_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text}, ensure_ascii=False),
                },
                timeout=15.0,
            )
        except httpx.RequestError as exc:
            raise _request_error("飞书消息接口请求失败", exc) from exc
        payload = _response_payload(response, "飞书消息接口请求失败")
        _raise_for_feishu_error(response, payload, "飞书消息接口请求失败")


def _message_text(notification: Notification) -> str:
    parts = [notification.title, notification.body]
    if notification.action_url:
        parts.append(f"查看详情：{settings.app_public_url.rstrip('/')}{notification.action_url}")
    return "\n".join(parts)


def deliver_pending_feishu_notifications(batch_size: int = 50) -> int:
    if not settings.feishu_notification_enabled:
        return 0
    db = SessionLocal()
    sent = 0
    try:
        now = utcnow()
        delivery_ids = list(
            db.scalars(
                select(NotificationDelivery.id)
                .where(
                    NotificationDelivery.channel == "feishu",
                    NotificationDelivery.status.in_(("pending", "retry")),
                    or_(
                        NotificationDelivery.next_attempt_at.is_(None),
                        NotificationDelivery.next_attempt_at <= now,
                    ),
                    NotificationDelivery.deleted_at.is_(None),
                )
                .order_by(NotificationDelivery.id)
                .limit(batch_size)
            ).all()
        )
        client = FeishuMessageClient()
        retry_minutes = (1, 5, 15, 60, 240)
        for delivery_id in delivery_ids:
            delivery = db.scalar(
                select(NotificationDelivery).where(NotificationDelivery.id == delivery_id)
            )
            if delivery is None or delivery.status not in {"pending", "retry"}:
                continue
            notification = delivery.notification
            delivery.attempts += 1
            delivery.updated_at = utcnow()
            try:
                if not delivery.receive_id or not delivery.receive_id_type:
                    raise FeishuMessageError("Feishu receiver is not synced")
                client.send_text(
                    delivery.receive_id,
                    delivery.receive_id_type,
                    _message_text(notification),
                )
            except FeishuMessageError as exc:
                delivery.last_error = str(exc)[:1000]
                if delivery.attempts >= len(retry_minutes):
                    delivery.status = "failed"
                    delivery.next_attempt_at = None
                else:
                    delivery.status = "retry"
                    delivery.next_attempt_at = utcnow() + timedelta(
                        minutes=retry_minutes[delivery.attempts - 1]
                    )
            else:
                delivery.status = "sent"
                delivery.sent_at = utcnow()
                delivery.next_attempt_at = None
                delivery.last_error = None
                sent += 1
            db.commit()
        return sent
    finally:
        db.close()
