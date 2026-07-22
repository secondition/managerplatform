from __future__ import annotations

import base64
import calendar
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from fastapi import HTTPException, Response, status

from app.core.config import settings

JWT_ALGORITHM = "HS256"
ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
OAUTH_STATE_COOKIE = "oauth_state"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc_epoch(value: datetime) -> int:
    """Epoch seconds treating a naive datetime as UTC.

    `datetime.utcnow()` is naive; calling `.timestamp()` on it wrongly assumes
    local time, which on non-UTC servers (e.g. Asia/Shanghai, UTC+8) skews JWT
    exp/iat by the offset and makes tokens expire immediately. `timegm` reads
    the value as UTC, matching PyJWT's clock.
    """
    return calendar.timegm(value.utctimetuple())


def create_access_token(user_id: int, token_version: int) -> str:
    now = utcnow()
    payload = {
        "sub": str(user_id),
        "type": "access",
        "token_version": token_version,
        "iat": _utc_epoch(now),
        "exp": _utc_epoch(now + timedelta(minutes=settings.access_token_ttl_minutes)),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session") from exc
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return payload


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def new_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_session_cookies(
    response: Response,
    *,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.access_token_ttl_minutes * 60,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.refresh_token_ttl_days * 24 * 60 * 60,
        path="/",
    )


def clear_session_cookies(response: Response) -> None:
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", samesite="strict", secure=settings.cookie_secure)


def set_oauth_state_cookie(response: Response, state: str) -> None:
    response.set_cookie(
        OAUTH_STATE_COOKIE,
        state,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=10 * 60,
        path="/api/v1/auth/feishu/callback",
    )


def clear_oauth_state_cookie(response: Response) -> None:
    response.delete_cookie(
        OAUTH_STATE_COOKIE,
        path="/api/v1/auth/feishu/callback",
        samesite="strict",
        secure=settings.cookie_secure,
    )


def sign_oauth_state() -> str:
    now = utcnow()
    body = {
        "nonce": secrets.token_urlsafe(24),
        "iat": _utc_epoch(now),
        "exp": _utc_epoch(now + timedelta(minutes=10)),
    }
    body_bytes = json.dumps(body, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(settings.jwt_secret.encode("utf-8"), body_bytes, hashlib.sha256).digest()
    return (
        base64.urlsafe_b64encode(body_bytes).decode("ascii").rstrip("=")
        + "."
        + base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    )


def verify_oauth_state(state: str) -> None:
    try:
        body_part, signature_part = state.split(".", 1)
        body_bytes = base64.urlsafe_b64decode(_pad_base64(body_part))
        expected = hmac.new(settings.jwt_secret.encode("utf-8"), body_bytes, hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(_pad_base64(signature_part))
        body = json.loads(body_bytes.decode("utf-8"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state") from exc

    if not hmac.compare_digest(expected, actual):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state")
    if int(body.get("exp", 0)) < _utc_epoch(utcnow()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state expired")


def _pad_base64(value: str) -> bytes:
    return (value + "=" * (-len(value) % 4)).encode("ascii")
