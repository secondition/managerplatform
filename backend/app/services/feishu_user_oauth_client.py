from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.core.config import Settings, settings

CHAT_USER_OAUTH_SCOPES = (
    "im:message",
    "im:message.send_as_user",
    "offline_access",
)
REQUIRED_CHAT_SCOPES = frozenset(CHAT_USER_OAUTH_SCOPES)


class FeishuUserOAuthError(RuntimeError):
    def __init__(self, category: str, *, permanent: bool = False) -> None:
        super().__init__(category)
        self.category = category
        self.permanent = permanent


@dataclass(frozen=True)
class FeishuOAuthToken:
    access_token: str
    access_expires_in: int
    refresh_token: str | None
    refresh_expires_in: int | None
    scopes: frozenset[str]
    open_id: str | None
    union_id: str | None


@dataclass(frozen=True)
class FeishuOAuthIdentity:
    open_id: str | None
    union_id: str | None


class FeishuUserOAuthClient:
    def __init__(self, runtime_settings: Settings = settings) -> None:
        self.settings = runtime_settings

    def build_authorize_url(self, state: str) -> str:
        query = urlencode(
            {
                "client_id": self.settings.feishu_app_id,
                "response_type": "code",
                "redirect_uri": self.settings.feishu_chat_oauth_redirect_uri,
                "scope": " ".join(CHAT_USER_OAUTH_SCOPES),
                "state": state,
            }
        )
        return (
            f"{self.settings.feishu_authorize_base}"
            f"{self.settings.feishu_authorize_path}?{query}"
        )

    async def exchange_authorization_code(self, code: str) -> FeishuOAuthToken:
        payload = await self._post_token(
            {
                "grant_type": "authorization_code",
                "client_id": self.settings.feishu_app_id,
                "client_secret": self.settings.feishu_app_secret,
                "code": code,
                "redirect_uri": self.settings.feishu_chat_oauth_redirect_uri,
            },
            operation="authorization",
        )
        token = self._parse_token(payload)
        if not token.refresh_token or token.refresh_expires_in is None:
            raise FeishuUserOAuthError("token_response_incomplete", permanent=True)
        return token

    async def refresh_access_token(
        self,
        refresh_token: str,
        *,
        fallback_scopes: frozenset[str],
    ) -> FeishuOAuthToken:
        payload = await self._post_token(
            {
                "grant_type": "refresh_token",
                "client_id": self.settings.feishu_app_id,
                "client_secret": self.settings.feishu_app_secret,
                "refresh_token": refresh_token,
            },
            operation="refresh",
        )
        return self._parse_token(payload, fallback_scopes=fallback_scopes)

    async def fetch_identity(self, access_token: str) -> FeishuOAuthIdentity:
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.feishu_api_base,
                timeout=10.0,
            ) as client:
                response = await client.get(
                    self.settings.feishu_user_info_path,
                    headers={"Authorization": f"Bearer {access_token}"},
                )
        except httpx.RequestError as exc:
            raise FeishuUserOAuthError("identity_service_unavailable") from exc
        payload = self._response_payload(response, operation="identity")
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        open_id = _optional_string(data.get("open_id"))
        union_id = _optional_string(data.get("union_id"))
        if not open_id and not union_id:
            raise FeishuUserOAuthError("identity_response_incomplete")
        return FeishuOAuthIdentity(open_id=open_id, union_id=union_id)

    async def _post_token(self, body: dict[str, str], *, operation: str) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                base_url=self.settings.feishu_api_base,
                timeout=10.0,
            ) as client:
                response = await client.post(self.settings.feishu_token_path, json=body)
        except httpx.RequestError as exc:
            raise FeishuUserOAuthError("token_service_unavailable") from exc
        return self._response_payload(response, operation=operation)

    def _response_payload(
        self,
        response: httpx.Response,
        *,
        operation: str,
    ) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise FeishuUserOAuthError("invalid_feishu_response") from exc
        if not isinstance(payload, dict):
            raise FeishuUserOAuthError("invalid_feishu_response")

        feishu_code = payload.get("code", 0)
        rejected = response.is_error or payload.get("error") or feishu_code not in (0, None)
        if rejected:
            oauth_error = str(payload.get("error") or "").lower()
            permanent = operation in {"authorization", "refresh"} and (
                400 <= response.status_code < 500
                or oauth_error
                in {
                    "invalid_grant",
                    "invalid_request",
                    "invalid_client",
                    "unauthorized_client",
                }
            )
            category = (
                "authorization_rejected"
                if operation == "authorization"
                else "refresh_rejected"
                if operation == "refresh"
                else "identity_rejected"
            )
            raise FeishuUserOAuthError(category, permanent=permanent)
        return payload

    def _parse_token(
        self,
        payload: dict[str, Any],
        *,
        fallback_scopes: frozenset[str] = frozenset(),
    ) -> FeishuOAuthToken:
        access_token = _optional_string(payload.get("access_token"))
        if not access_token:
            raise FeishuUserOAuthError("token_response_incomplete")
        access_expires_in = _positive_seconds(payload, "expires_in", "expires")

        refresh_token = _optional_string(payload.get("refresh_token"))
        refresh_expiry_present = any(
            key in payload
            for key in ("refresh_token_expires_in", "refresh_expires_in")
        )
        refresh_expires_in = (
            _positive_seconds(
                payload,
                "refresh_token_expires_in",
                "refresh_expires_in",
            )
            if refresh_expiry_present
            else None
        )
        scopes = _parse_scopes(payload.get("scope")) or fallback_scopes
        return FeishuOAuthToken(
            access_token=access_token,
            access_expires_in=access_expires_in,
            refresh_token=refresh_token,
            refresh_expires_in=refresh_expires_in,
            scopes=scopes,
            open_id=_optional_string(payload.get("open_id")),
            union_id=_optional_string(payload.get("union_id")),
        )


def missing_required_chat_scopes(scopes: frozenset[str]) -> list[str]:
    return sorted(REQUIRED_CHAT_SCOPES - scopes)


def _positive_seconds(payload: dict[str, Any], *keys: str) -> int:
    value: Any = None
    for key in keys:
        if key in payload:
            value = payload[key]
            break
    if isinstance(value, bool):
        raise FeishuUserOAuthError("token_expiry_invalid")
    try:
        seconds = int(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise FeishuUserOAuthError("token_expiry_invalid") from exc
    if seconds <= 0:
        raise FeishuUserOAuthError("token_expiry_invalid")
    return seconds


def _parse_scopes(value: Any) -> frozenset[str]:
    if isinstance(value, str):
        return frozenset(item for item in value.replace(",", " ").split() if item)
    if isinstance(value, list):
        return frozenset(item.strip() for item in value if isinstance(item, str) and item.strip())
    return frozenset()


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
