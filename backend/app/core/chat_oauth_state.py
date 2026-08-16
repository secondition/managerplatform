from __future__ import annotations

import base64
import binascii
import calendar
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlencode, urlsplit

from fastapi import Response

from app.core.config import Settings, settings
from app.core.security import utcnow

CHAT_OAUTH_PURPOSE = "agent_user_authorization"
CHAT_OAUTH_STATE_COOKIE = "feishu_chat_oauth_state"
CHAT_OAUTH_CALLBACK_PATH = "/api/v1/chat/feishu/callback"
CHAT_OAUTH_STATE_TTL_MINUTES = 10


class ChatOAuthStateError(ValueError):
    pass


@dataclass(frozen=True)
class ChatOAuthState:
    purpose: str
    agent_key: str
    user_id: int
    return_to: str
    nonce: str
    issued_at: int
    expires_at: int


def build_chat_return_to(agent_key: str) -> str:
    return f"/chat?{urlencode({'agent': agent_key})}"


def sign_chat_oauth_state(
    *,
    agent_key: str,
    user_id: int,
    return_to: str,
    runtime_settings: Settings = settings,
    now: datetime | None = None,
) -> str:
    issued = now or utcnow()
    _validate_return_to(return_to, agent_key)
    body = {
        "purpose": CHAT_OAUTH_PURPOSE,
        "agent_key": agent_key,
        "user_id": user_id,
        "return_to": return_to,
        "nonce": secrets.token_urlsafe(24),
        "iat": _utc_epoch(issued),
        "exp": _utc_epoch(issued + timedelta(minutes=CHAT_OAUTH_STATE_TTL_MINUTES)),
    }
    body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
    signature = hmac.new(
        runtime_settings.jwt_secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256,
    ).digest()
    return f"{_encode_base64(body_bytes)}.{_encode_base64(signature)}"


def verify_chat_oauth_state(
    state: str,
    *,
    runtime_settings: Settings = settings,
    now: datetime | None = None,
) -> ChatOAuthState:
    try:
        body_part, signature_part = state.split(".", 1)
        body_bytes = base64.urlsafe_b64decode(_pad_base64(body_part))
        actual_signature = base64.urlsafe_b64decode(_pad_base64(signature_part))
        body = json.loads(body_bytes.decode("utf-8"))
    except (
        UnicodeDecodeError,
        UnicodeEncodeError,
        ValueError,
        binascii.Error,
        json.JSONDecodeError,
    ) as exc:
        raise ChatOAuthStateError("Invalid chat OAuth state") from exc

    expected_signature = hmac.new(
        runtime_settings.jwt_secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256,
    ).digest()
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise ChatOAuthStateError("Invalid chat OAuth state")

    purpose = body.get("purpose")
    agent_key = body.get("agent_key")
    user_id = body.get("user_id")
    return_to = body.get("return_to")
    nonce = body.get("nonce")
    issued_at = body.get("iat")
    expires_at = body.get("exp")
    if (
        purpose != CHAT_OAUTH_PURPOSE
        or not isinstance(agent_key, str)
        or not agent_key
        or not isinstance(user_id, int)
        or isinstance(user_id, bool)
        or user_id <= 0
        or not isinstance(return_to, str)
        or not isinstance(nonce, str)
        or not nonce
        or not isinstance(issued_at, int)
        or isinstance(issued_at, bool)
        or not isinstance(expires_at, int)
        or isinstance(expires_at, bool)
    ):
        raise ChatOAuthStateError("Invalid chat OAuth state")

    current_epoch = _utc_epoch(now or utcnow())
    if expires_at < current_epoch:
        raise ChatOAuthStateError("Chat OAuth state expired")
    if issued_at > current_epoch + 60:
        raise ChatOAuthStateError("Invalid chat OAuth state")
    if expires_at <= issued_at or expires_at - issued_at > CHAT_OAUTH_STATE_TTL_MINUTES * 60:
        raise ChatOAuthStateError("Invalid chat OAuth state")
    _validate_return_to(return_to, agent_key)
    return ChatOAuthState(
        purpose=purpose,
        agent_key=agent_key,
        user_id=user_id,
        return_to=return_to,
        nonce=nonce,
        issued_at=issued_at,
        expires_at=expires_at,
    )


def set_chat_oauth_state_cookie(
    response: Response,
    state: str,
    *,
    runtime_settings: Settings = settings,
) -> None:
    response.set_cookie(
        CHAT_OAUTH_STATE_COOKIE,
        state,
        httponly=True,
        secure=runtime_settings.cookie_secure,
        samesite="strict",
        max_age=CHAT_OAUTH_STATE_TTL_MINUTES * 60,
        path=CHAT_OAUTH_CALLBACK_PATH,
    )


def clear_chat_oauth_state_cookie(
    response: Response,
    *,
    runtime_settings: Settings = settings,
) -> None:
    response.delete_cookie(
        CHAT_OAUTH_STATE_COOKIE,
        path=CHAT_OAUTH_CALLBACK_PATH,
        samesite="strict",
        secure=runtime_settings.cookie_secure,
    )


def _validate_return_to(return_to: str, agent_key: str) -> None:
    parsed = urlsplit(return_to)
    query = parse_qs(parsed.query, keep_blank_values=True)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.path != "/chat"
        or parsed.fragment
        or set(query) != {"agent"}
        or query["agent"] != [agent_key]
    ):
        raise ChatOAuthStateError("Invalid chat OAuth return path")


def _utc_epoch(value: datetime) -> int:
    return calendar.timegm(value.utctimetuple())


def _encode_base64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _pad_base64(value: str) -> bytes:
    return (value + "=" * (-len(value) % 4)).encode("ascii")
