from __future__ import annotations

import json
from typing import Any

import httpx

from app.core.config import Settings, settings


class FeishuUserMessageError(RuntimeError):
    def __init__(self, code: str, *, retryable: bool) -> None:
        super().__init__(code)
        self.code = code
        self.retryable = retryable


class FeishuUserMessageClient:
    def __init__(
        self,
        runtime_settings: Settings = settings,
        *,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self.settings = runtime_settings
        self._client = http_client
        self._owns_client = http_client is None

    async def aclose(self) -> None:
        if self._client is not None and self._owns_client:
            await self._client.aclose()
        self._client = None

    async def send_text(
        self,
        *,
        access_token: str,
        chat_id: str,
        text: str,
        request_uuid: str,
    ) -> str:
        try:
            response = await self._http_client().post(
                "/open-apis/im/v1/messages",
                params={"receive_id_type": "chat_id"},
                headers={"Authorization": f"Bearer {access_token}"},
                json={
                    "receive_id": chat_id,
                    "msg_type": "text",
                    "content": json.dumps({"text": text}, ensure_ascii=False),
                    "uuid": request_uuid,
                },
            )
        except httpx.RequestError as exc:
            raise FeishuUserMessageError("send_network_error", retryable=True) from exc
        if response.status_code == 429:
            raise FeishuUserMessageError("send_rate_limited", retryable=True)
        if response.status_code >= 500:
            raise FeishuUserMessageError("send_service_unavailable", retryable=True)
        if response.status_code in {401, 403}:
            raise FeishuUserMessageError("authorization_required", retryable=False)
        if response.status_code >= 400:
            raise FeishuUserMessageError("send_rejected", retryable=False)
        payload = _json_payload(response)
        code = payload.get("code", 0)
        if code not in {0, None}:
            raise FeishuUserMessageError("send_rejected", retryable=False)
        data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
        message_id = _optional_string(data.get("message_id"))
        if not message_id:
            raise FeishuUserMessageError("send_response_incomplete", retryable=True)
        return message_id

    def _http_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.settings.feishu_api_base,
                timeout=20.0,
            )
        return self._client


def _json_payload(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as exc:
        raise FeishuUserMessageError("send_response_invalid", retryable=True) from exc
    if not isinstance(payload, dict):
        raise FeishuUserMessageError("send_response_invalid", retryable=True)
    return payload


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
