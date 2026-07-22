import hmac
from datetime import timedelta

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, get_current_user, get_user_permissions
from app.core.config import settings
from app.core.security import (
    REFRESH_COOKIE,
    OAUTH_STATE_COOKIE,
    clear_oauth_state_cookie,
    clear_session_cookies,
    create_access_token,
    hash_token,
    new_csrf_token,
    new_refresh_token,
    set_oauth_state_cookie,
    set_session_cookies,
    sign_oauth_state,
    utcnow,
    verify_oauth_state,
)
from app.db.session import get_db
from app.models.user import RefreshToken, User
from app.schemas.auth import FeishuCallbackIn, FeishuLoginConfig
from app.schemas.user import AuthUserResponse
from app.services.feishu_auth_service import FeishuAuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/feishu/login-config", response_model=FeishuLoginConfig)
def feishu_login_config(response: Response) -> FeishuLoginConfig:
    # Build the full authorize URL server-side (urlencode, never manual concat).
    state = sign_oauth_state()
    set_oauth_state_cookie(response, state)
    return FeishuLoginConfig(
        app_id=settings.feishu_app_id,
        redirect_uri=settings.feishu_redirect_uri,
        state=state,
        authorize_url=settings.build_authorize_url(state),
    )


@router.post("/feishu/callback", response_model=AuthUserResponse)
async def feishu_callback(
    payload: FeishuCallbackIn,
    request: Request,
    response: Response,
    oauth_state: str | None = Cookie(default=None, alias=OAUTH_STATE_COOKIE),
    db: Session = Depends(get_db),
) -> AuthUserResponse:
    if not oauth_state or not hmac.compare_digest(payload.state, oauth_state):
        clear_oauth_state_cookie(response)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state mismatch")
    clear_oauth_state_cookie(response)
    verify_oauth_state(payload.state)
    user, permissions, csrf_token = await FeishuAuthService(db).login_with_code(
        code=payload.code,
        request=request,
        response=response,
    )
    return AuthUserResponse(user=user, permissions=permissions, csrf_token=csrf_token)


@router.get("/me", response_model=AuthUserResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AuthUserResponse:
    return AuthUserResponse(user=user, permissions=get_user_permissions(user, db), csrf_token=None)


@router.post("/refresh", response_model=AuthUserResponse, dependencies=[Depends(csrf_protect)])
def refresh_session(
    response: Response,
    request: Request,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    db: Session = Depends(get_db),
) -> AuthUserResponse:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    token_row = db.scalar(
        select(RefreshToken).where(
            RefreshToken.token_hash == hash_token(refresh_token),
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > utcnow(),
            RefreshToken.deleted_at.is_(None),
        )
    )
    if token_row is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = db.scalar(select(User).where(User.id == token_row.user_id, User.deleted_at.is_(None)))
    if user is None or user.status != "active":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh user")

    replacement_token = new_refresh_token()
    token_row.revoked_at = utcnow()
    token_row.updated_by = user.id
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_token(replacement_token),
            user_agent=request.headers.get("user-agent", "")[:300],
            expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
            created_by=user.id,
            updated_by=user.id,
        )
    )
    db.commit()

    csrf_token = new_csrf_token()
    set_session_cookies(
        response,
        access_token=create_access_token(user.id, user.token_version),
        refresh_token=replacement_token,
        csrf_token=csrf_token,
    )
    return AuthUserResponse(user=user, permissions=get_user_permissions(user, db), csrf_token=csrf_token)


@router.post("/logout", dependencies=[Depends(csrf_protect)])
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    if refresh_token:
        token_row = db.scalar(
            select(RefreshToken).where(
                RefreshToken.token_hash == hash_token(refresh_token),
                RefreshToken.revoked_at.is_(None),
            )
        )
        if token_row is not None and token_row.user_id == user.id:
            token_row.revoked_at = utcnow()
            token_row.updated_by = user.id
            db.commit()
    clear_session_cookies(response)
    return {"ok": True}
