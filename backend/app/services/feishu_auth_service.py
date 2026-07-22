from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

import httpx
from fastapi import HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import DEFAULT_FEATURE_PERMISSIONS
from app.core.security import (
    create_access_token,
    hash_token,
    new_csrf_token,
    new_refresh_token,
    set_session_cookies,
    utcnow,
)
from app.models.user import RefreshToken, User, UserPermission


@dataclass(frozen=True)
class FeishuUserInfo:
    union_id: str
    open_id: str
    user_id: str | None
    name: str
    email: str | None
    avatar_url: str | None


class FeishuAuthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    async def login_with_code(
        self,
        *,
        code: str,
        request: Request,
        response: Response,
    ) -> tuple[User, list[str], str]:
        info = await self._fetch_user_info(code)
        user = self._find_roster_user_or_bootstrap_owner(info)
        if user.status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")

        if settings.feishu_sync_profile_on_login:
            self._sync_profile(user, info)

        user.last_login_at = utcnow()
        self.db.flush()

        permissions = self._enabled_permissions(user)
        refresh_token = new_refresh_token()
        refresh = RefreshToken(
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            user_agent=request.headers.get("user-agent", "")[:300],
            expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
            created_by=user.id,
            updated_by=user.id,
        )
        self.db.add(refresh)
        self.db.commit()
        self.db.refresh(user)

        access_token = create_access_token(user.id, user.token_version)
        csrf_token = new_csrf_token()
        set_session_cookies(
            response,
            access_token=access_token,
            refresh_token=refresh_token,
            csrf_token=csrf_token,
        )
        return user, permissions, csrf_token

    async def _fetch_user_info(self, code: str) -> FeishuUserInfo:
        async with httpx.AsyncClient(base_url=settings.feishu_api_base, timeout=10.0) as client:
            # 新版 OAuth2：授权码直接换 user_access_token，不再先换 app_access_token。
            token_resp = await client.post(
                settings.feishu_token_path,
                json={
                    "grant_type": "authorization_code",
                    "client_id": settings.feishu_app_id,
                    "client_secret": settings.feishu_app_secret,
                    "code": code,
                    "redirect_uri": settings.feishu_redirect_uri,
                },
            )
            user_access_token = self._extract_access_token(token_resp)

            user_info_resp = await client.get(
                settings.feishu_user_info_path,
                headers={"Authorization": f"Bearer {user_access_token}"},
            )
            user_info = self._checked_feishu_response(user_info_resp)

        union_id = user_info.get("union_id")
        open_id = user_info.get("open_id")
        name = user_info.get("name")
        if not union_id or not open_id or not name:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Feishu user info missing required fields",
            )

        return FeishuUserInfo(
            union_id=union_id,
            open_id=open_id,
            user_id=user_info.get("user_id"),
            name=name,
            email=user_info.get("email"),
            avatar_url=user_info.get("avatar_url"),
        )

    def _checked_feishu_response(self, response: httpx.Response) -> dict:
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Feishu request failed") from exc

        code = payload.get("code", 0)
        if code not in (0, None):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=payload.get("msg") or "Feishu request rejected",
            )
        data = payload.get("data")
        if not isinstance(data, dict):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Feishu response missing data",
            )
        return data

    def _extract_access_token(self, response: httpx.Response) -> str:
        """Pull user_access_token from the v2 OAuth2 token response.

        /authen/v2/oauth/token follows the OAuth2 standard: access_token at the
        top level of a 200 response, an error status otherwise.
        """
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Feishu token request failed") from exc

        token = payload.get("access_token")
        if not token:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Feishu token response missing access_token",
            )
        return token

    def _find_roster_user_or_bootstrap_owner(self, info: FeishuUserInfo) -> User:
        user = self.db.scalar(
            select(User).where(User.feishu_union_id == info.union_id, User.deleted_at.is_(None))
        )
        if user is not None:
            if settings.owner_feishu_union_id and info.union_id == settings.owner_feishu_union_id:
                user.role = "owner"
            return user

        existing_user_id = self.db.scalar(select(User.id).where(User.deleted_at.is_(None)).limit(1))
        if existing_user_id is not None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not in synced company roster",
            )

        if not settings.owner_feishu_union_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OWNER_FEISHU_UNION_ID is required for first login",
            )
        if info.union_id != settings.owner_feishu_union_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the configured owner can initialize this workspace",
            )

        role = self._resolve_initial_role(info)
        user = User(
            name=info.name,
            email=info.email,
            avatar_url=info.avatar_url,
            role=role,
            feishu_union_id=info.union_id,
            feishu_open_id=info.open_id,
            feishu_user_id=info.user_id,
            status="active",
            sync_source="feishu",
        )
        self.db.add(user)
        self.db.flush()
        self._grant_default_permissions(user)
        return user

    def _resolve_initial_role(self, info: FeishuUserInfo) -> str:
        if settings.owner_feishu_union_id and info.union_id == settings.owner_feishu_union_id:
            return "owner"
        return "member"

    def _grant_default_permissions(self, user: User) -> None:
        # Feature permissions apply by row for everyone (owner included, so they
        # can toggle their own). Owner still bypasses admin:* via role.
        wanted = list(dict.fromkeys(DEFAULT_FEATURE_PERMISSIONS + settings.default_permissions))
        for permission in wanted:
            self.db.add(
                UserPermission(
                    user_id=user.id,
                    permission=permission,
                    enabled=True,
                    created_by=user.id,
                    updated_by=user.id,
                )
            )

    def _sync_profile(self, user: User, info: FeishuUserInfo) -> None:
        user.name = info.name
        user.email = info.email
        if not (user.avatar_url or "").startswith("/uploads/avatars/"):
            user.avatar_url = info.avatar_url
        user.feishu_open_id = info.open_id
        user.feishu_user_id = info.user_id
        user.updated_by = user.id

    def _enabled_permissions(self, user: User) -> list[str]:
        rows = self.db.scalars(
            select(UserPermission.permission).where(
                UserPermission.user_id == user.id,
                UserPermission.enabled.is_(True),
                UserPermission.deleted_at.is_(None),
            )
        ).all()
        return list(rows)
