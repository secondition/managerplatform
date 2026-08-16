from __future__ import annotations

import math
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import Settings, settings
from app.core.security import utcnow


class FeishuTenantError(RuntimeError):
    def __init__(
        self,
        category: str,
        *,
        retryable: bool,
        rate_limited: bool = False,
        retry_after_seconds: int | None = None,
        log_id: str | None = None,
    ) -> None:
        super().__init__(category)
        self.category = category
        self.retryable = retryable
        self.rate_limited = rate_limited
        self.retry_after_seconds = retry_after_seconds
        self.log_id = log_id


@dataclass(frozen=True)
class FeishuPage:
    items: tuple[dict[str, Any], ...]
    has_more: bool
    page_token: str | None


class FeishuTenantClient:
    def __init__(
        self,
        runtime_settings: Settings = settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = runtime_settings
        self._client = http_client
        self._owns_client = http_client is None
        self._tenant_token: str | None = None
        self._tenant_token_expires_at = None

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        self._client = None

    async def get_chat(self, chat_id: str) -> dict[str, Any]:
        return await self._tenant_get(
            f"/open-apis/im/v1/chats/{chat_id}",
            rejection_categories={"230027": "chat_permission_missing"},
        )

    async def list_chat_members_page(
        self,
        chat_id: str,
        *,
        page_token: str | None = None,
    ) -> FeishuPage:
        params: dict[str, Any] = {
            "page_size": 100,
            "member_id_type": "open_id",
        }
        if page_token:
            params["page_token"] = page_token
        data = await self._tenant_get(
            f"/open-apis/im/v1/chats/{chat_id}/members",
            params=params,
            rejection_categories={"230027": "member_permission_missing"},
        )
        return self._parse_page(data)

    async def list_chat_messages_page(
        self,
        chat_id: str,
        *,
        start_time_ms: int,
        end_time_ms: int,
        page_token: str | None = None,
    ) -> FeishuPage:
        params: dict[str, Any] = {
            "container_id_type": "chat",
            "container_id": chat_id,
            "sort_type": "ByCreateTimeAsc",
            "page_size": 50,
            "start_time": str(max(0, start_time_ms // 1000)),
            "end_time": str(max(0, end_time_ms // 1000)),
        }
        if page_token:
            params["page_token"] = page_token
        data = await self._tenant_get(
            "/open-apis/im/v1/messages",
            params=params,
            rejection_categories={
                "230002": "chat_bot_not_in_group",
                "230006": "chat_bot_disabled",
                "230027": "message_permission_missing",
                "231203": "chat_history_unavailable",
            },
        )
        return self._parse_page(data)

    async def open_message_resource(
        self,
        message_id: str,
        file_key: str,
    ) -> httpx.Response:
        path = (
            f"/open-apis/im/v1/messages/{quote(message_id, safe='')}/resources/"
            f"{quote(file_key, safe='')}"
        )
        for attempt in range(2):
            response: httpx.Response | None = None
            try:
                token = await self._tenant_access_token()
                request = self._http_client().build_request(
                    "GET",
                    path,
                    params={"type": "file"},
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept-Encoding": "identity",
                    },
                )
                response = await self._http_client().send(request, stream=True)
                self._raise_stream_error(response, allow_auth_rejection=True)
                return response
            except FeishuTenantError as exc:
                if response is not None:
                    await response.aclose()
                if attempt == 0 and exc.category == "tenant_token_rejected":
                    self._tenant_token = None
                    self._tenant_token_expires_at = None
                    continue
                raise
            except httpx.RequestError as exc:
                if response is not None:
                    await response.aclose()
                raise FeishuTenantError(
                    "resource_network_error",
                    retryable=True,
                ) from exc
        raise FeishuTenantError("tenant_token_rejected", retryable=True)

    async def _tenant_get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        rejection_categories: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        for attempt in range(2):
            try:
                token = await self._tenant_access_token()
                response = await self._request(
                    "GET",
                    path,
                    params=params,
                    headers={"Authorization": f"Bearer {token}"},
                    category="tenant_request_failed",
                    allow_auth_rejection=True,
                    rejection_categories=rejection_categories,
                )
                return self._extract_data(
                    response,
                    rejection_categories=rejection_categories,
                )
            except FeishuTenantError as exc:
                if attempt == 0 and exc.category == "tenant_token_rejected":
                    self._tenant_token = None
                    self._tenant_token_expires_at = None
                    continue
                raise
        raise FeishuTenantError("tenant_token_rejected", retryable=True)

    async def _tenant_access_token(self) -> str:
        now = utcnow()
        if (
            self._tenant_token
            and self._tenant_token_expires_at
            and self._tenant_token_expires_at > now
        ):
            return self._tenant_token

        response = await self._request(
            "POST",
            self.settings.feishu_tenant_token_path,
            json={
                "app_id": self.settings.feishu_app_id,
                "app_secret": self.settings.feishu_app_secret,
            },
            category="tenant_token_failed",
        )
        payload = self._parse_payload(response)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        token = payload.get("tenant_access_token") or data.get("tenant_access_token")
        if not isinstance(token, str) or not token:
            raise FeishuTenantError("tenant_token_incomplete", retryable=True)
        expires_in = _positive_int(payload.get("expire") or data.get("expire") or 7200)
        self._tenant_token = token
        self._tenant_token_expires_at = now + timedelta(
            seconds=max(60, expires_in - 300)
        )
        return token

    async def _request(
        self,
        method: str,
        path: str,
        *,
        category: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        allow_auth_rejection: bool = False,
        rejection_categories: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            response = await self._http_client().request(
                method,
                path,
                params=params,
                json=json,
                headers=headers,
            )
        except httpx.RequestError as exc:
            raise FeishuTenantError(category, retryable=True) from exc
        if response.status_code == 429:
            raise FeishuTenantError(
                "rate_limited",
                retryable=True,
                rate_limited=True,
                retry_after_seconds=_retry_after_seconds(response),
                log_id=_response_log_id(response),
            )
        if response.status_code >= 500:
            raise FeishuTenantError(
                "feishu_service_unavailable",
                retryable=True,
                log_id=_response_log_id(response),
            )
        if response.status_code >= 400:
            if allow_auth_rejection and response.status_code == 401:
                raise FeishuTenantError("tenant_token_rejected", retryable=True)
            rejection_category = _response_rejection_category(
                response,
                rejection_categories,
            )
            raise FeishuTenantError(
                rejection_category or "feishu_request_rejected",
                retryable=False,
                log_id=_response_log_id(response),
            )
        return response

    def _extract_data(
        self,
        response: httpx.Response,
        *,
        rejection_categories: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload = self._parse_payload(
            response,
            allow_token_rejection=True,
            rejection_categories=rejection_categories,
        )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise FeishuTenantError("feishu_response_incomplete", retryable=True)
        return data

    def _raise_stream_error(
        self,
        response: httpx.Response,
        *,
        allow_auth_rejection: bool,
    ) -> None:
        if response.status_code == 429:
            raise FeishuTenantError(
                "rate_limited",
                retryable=True,
                rate_limited=True,
                retry_after_seconds=_retry_after_seconds(response),
                log_id=_response_log_id(response),
            )
        if response.status_code >= 500:
            raise FeishuTenantError(
                "feishu_service_unavailable",
                retryable=True,
                log_id=_response_log_id(response),
            )
        if response.status_code >= 400:
            if allow_auth_rejection and response.status_code == 401:
                raise FeishuTenantError("tenant_token_rejected", retryable=True)
            raise FeishuTenantError(
                "resource_unavailable",
                retryable=response.status_code in {408, 425},
                log_id=_response_log_id(response),
            )

    def _parse_payload(
        self,
        response: httpx.Response,
        *,
        allow_token_rejection: bool = False,
        rejection_categories: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise FeishuTenantError("feishu_response_invalid", retryable=True) from exc
        if not isinstance(payload, dict):
            raise FeishuTenantError("feishu_response_invalid", retryable=True)
        code = payload.get("code", 0)
        if code not in (0, None):
            normalized_code = str(code)
            if allow_token_rejection and normalized_code in {
                "99991400",
                "99991401",
                "99991402",
                "99991403",
            }:
                raise FeishuTenantError("tenant_token_rejected", retryable=True)
            raise FeishuTenantError(
                (rejection_categories or {}).get(
                    normalized_code,
                    "feishu_request_rejected",
                ),
                retryable=False,
                log_id=_response_log_id(response),
            )
        return payload

    def _parse_page(self, data: dict[str, Any]) -> FeishuPage:
        raw_items = data.get("items") or []
        if not isinstance(raw_items, list):
            raise FeishuTenantError("feishu_page_invalid", retryable=True)
        items = tuple(item for item in raw_items if isinstance(item, dict))
        has_more = bool(data.get("has_more"))
        raw_page_token = data.get("page_token")
        page_token = raw_page_token if isinstance(raw_page_token, str) and raw_page_token else None
        if has_more and not page_token:
            raise FeishuTenantError("feishu_page_token_missing", retryable=True)
        if page_token and len(page_token) > 500:
            raise FeishuTenantError("feishu_page_token_invalid", retryable=True)
        return FeishuPage(items=items, has_more=has_more, page_token=page_token)

    def _http_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.feishu_api_base,
                timeout=20.0,
            )
        return self._client


def _retry_after_seconds(response: httpx.Response) -> int | None:
    raw_value = response.headers.get("x-ogw-ratelimit-reset") or response.headers.get(
        "retry-after"
    )
    if not raw_value:
        return None
    try:
        value = float(raw_value)
    except ValueError:
        return None
    if not math.isfinite(value) or value < 0:
        return None
    current_epoch = time.time()
    if value > 1_000_000_000_000:
        value /= 1000
    if value > 10_000_000:
        value = max(0, value - current_epoch)
    return max(1, min(3600, math.ceil(value)))


def _response_log_id(response: httpx.Response) -> str | None:
    value = response.headers.get("x-tt-logid") or response.headers.get("x-request-id")
    if not value:
        return None
    return value[:160]


def _response_rejection_category(
    response: httpx.Response,
    rejection_categories: dict[str, str] | None,
) -> str | None:
    if not rejection_categories:
        return None
    try:
        payload = response.json()
    except ValueError:
        return None
    if not isinstance(payload, dict):
        return None
    return rejection_categories.get(str(payload.get("code")))


def _positive_int(value: Any) -> int:
    if isinstance(value, bool):
        return 7200
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return 7200
    return parsed if parsed > 0 else 7200
