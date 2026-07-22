from collections.abc import Callable

from fastapi import Cookie, Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import ACCESS_COOKIE, CSRF_COOKIE, decode_access_token
from app.db.session import get_db
from app.models.user import User, UserPermission


def get_current_user(
    access_token: str | None = Cookie(default=None, alias=ACCESS_COOKIE),
    db: Session = Depends(get_db),
) -> User:
    if not access_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    payload = decode_access_token(access_token)
    user_id = int(payload["sub"])
    user = db.scalar(select(User).where(User.id == user_id, User.deleted_at.is_(None)))
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if user.status != "active":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User disabled")
    if payload.get("token_version") != user.token_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session expired")
    return user


def csrf_protect(
    request: Request,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    csrf_cookie: str | None = Cookie(default=None, alias=CSRF_COOKIE),
) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not csrf_cookie or not x_csrf_token or csrf_cookie != x_csrf_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF token mismatch")


def get_user_permissions(user: User, db: Session) -> list[str]:
    rows = db.scalars(
        select(UserPermission.permission).where(
            UserPermission.user_id == user.id,
            UserPermission.enabled.is_(True),
            UserPermission.deleted_at.is_(None),
        )
    ).all()
    return list(rows)


def require_permission(permission: str) -> Callable[[User, Session], User]:
    def dependency(
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db),
    ) -> User:
        # Owner bypasses advanced (admin:*) gates so they can never lock
        # themselves out of the backend, but feature:* gates apply by row —
        # owner may toggle their own feature access and it takes effect.
        if user.role == "owner" and permission.startswith("admin:"):
            return user
        permissions = get_user_permissions(user, db)
        if permission not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing permission")
        return user

    return dependency
