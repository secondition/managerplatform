import hmac
import asyncio
import json
import time
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    Query,
    status,
)
from fastapi.responses import JSONResponse
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, get_current_user
from app.core.chat_oauth_state import (
    CHAT_OAUTH_STATE_COOKIE,
    ChatOAuthStateError,
    build_chat_return_to,
    clear_chat_oauth_state_cookie,
    set_chat_oauth_state_cookie,
    sign_chat_oauth_state,
    verify_chat_oauth_state,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.chat import (
    ChatAgentStatusOut,
    ChatAgentSummaryOut,
    ChatAuthorizeOut,
    ChatDisconnectOut,
    ChatOAuthCallbackIn,
    ChatOAuthCallbackOut,
    ChatMessagePageOut,
    SendChatMessageIn,
    SendChatMessageOut,
)
from app.services.agent_access_service import AgentAccessService
from app.services.chat_attachment_service import ChatAttachmentError, ChatAttachmentService
from app.services.chat_event_service import ChatEventWatcher, serialize_sse
from app.services.chat_message_send_service import ChatMessageSendService, ChatSendError
from app.services.chat_projection_service import ChatProjectionError, ChatProjectionService
from app.services.feishu_user_credential_service import (
    FeishuCredentialError,
    FeishuUserCredentialService,
)

router = APIRouter(prefix="/chat", tags=["chat"])
_SSE_CHECK_INTERVAL_SECONDS = 20
_MAX_SEND_REQUEST_BYTES = 1_000_000


@router.get("/agents", response_model=list[ChatAgentSummaryOut])
def list_agents(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    service = AgentAccessService(db)
    return [
        {
            "agent_key": agent.agent_key,
            "name": agent.name,
            "description": agent.description,
            "avatar_url": agent.avatar_url,
            "implementation_type": agent.implementation_type,
            "platform_granted": True,
            "status": service.runtime_status(user, agent).availability,
        }
        for agent in service.list_platform_granted_agents(user)
    ]


@router.get("/agents/{agent_key}/status", response_model=ChatAgentStatusOut)
def get_agent_status(
    agent_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    service = AgentAccessService(db)
    agent = service.get_granted_agent(user, agent_key)
    runtime = service.runtime_status(user, agent)
    return {
        "agent_key": agent.agent_key,
        "platform_granted": True,
        "credential_status": runtime.credential_status,
        "membership_status": runtime.membership_status,
        "sync_status": runtime.sync_status,
        "can_read": runtime.can_read,
        "can_send": runtime.can_send,
        "blocked_reason": runtime.blocked_reason,
        "last_sync_at": runtime.last_sync_at,
        "sync_delay_seconds": runtime.sync_delay_seconds,
    }


@router.get(
    "/agents/{agent_key}/messages",
    response_model=ChatMessagePageOut,
)
def list_agent_messages(
    agent_key: str,
    cursor: str | None = Query(default=None, max_length=500),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    access_service = AgentAccessService(db)
    agent = access_service.get_granted_agent(user, agent_key)
    runtime = access_service.runtime_status(user, agent)
    if not runtime.can_read:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": runtime.blocked_reason or "chat_unavailable"},
        )
    try:
        page = ChatProjectionService(db).list_messages(
            user,
            agent,
            cursor=cursor,
            limit=limit,
        )
    except ChatProjectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": exc.code},
        ) from exc
    return {
        "items": list(page.items),
        "next_cursor": page.next_cursor,
        "has_more": page.has_more,
    }


@router.post(
    "/agents/{agent_key}/messages",
    response_model=SendChatMessageOut,
    dependencies=[Depends(csrf_protect)],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": SendChatMessageIn.model_json_schema(),
                }
            },
        }
    },
)
async def send_agent_message(
    agent_key: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SendChatMessageOut:
    try:
        raw_body = await request.body()
        if len(raw_body) > _MAX_SEND_REQUEST_BYTES:
            raise ValueError
        raw_payload = json.loads(raw_body)
        payload = SendChatMessageIn.model_validate(raw_payload)
    except (UnicodeError, ValueError, ValidationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": "invalid_message_request"},
        ) from exc
    access_service = AgentAccessService(db)
    agent = access_service.get_granted_agent(user, agent_key)
    runtime = access_service.runtime_status(user, agent)
    if not runtime.can_send:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": runtime.blocked_reason or "chat_send_unavailable"},
        )
    try:
        result = await ChatMessageSendService(db).send(
            user,
            agent,
            text=payload.text,
            client_request_id=payload.client_request_id,
        )
    except ChatSendError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={"code": exc.code},
        ) from exc
    return SendChatMessageOut(
        client_request_id=result.client_request_id,
        status=result.status,
        message_id=result.message_id,
        error_code=result.error_code,
        error_message=result.error_message,
    )


@router.get(
    "/agents/{agent_key}/messages/{message_id}/attachment",
)
async def download_agent_attachment(
    agent_key: str,
    message_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    access_service = AgentAccessService(db)
    agent = access_service.get_granted_agent(user, agent_key)
    runtime = access_service.runtime_status(user, agent)
    if not runtime.can_read:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": runtime.blocked_reason or "chat_unavailable"},
        )
    try:
        download = await ChatAttachmentService(db).open_download(
            user,
            agent,
            message_id,
        )
    except ChatAttachmentError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code},
        ) from exc
    encoded_name = quote(download.file_name, safe="")
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_name}",
        "Content-Length": str(download.content_length),
        "X-Content-Type-Options": "nosniff",
        "Cache-Control": "private, no-store",
    }
    return StreamingResponse(
        download.iter_bytes(),
        media_type=download.content_type,
        headers=headers,
        background=BackgroundTask(download.aclose),
    )


@router.get("/agents/{agent_key}/events")
async def stream_agent_events(
    agent_key: str,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> StreamingResponse:
    access_service = AgentAccessService(db)
    agent = access_service.get_granted_agent(user, agent_key)
    runtime = access_service.runtime_status(user, agent)
    if not runtime.can_read:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": runtime.blocked_reason or "chat_unavailable"},
        )
    watcher = ChatEventWatcher(db, user, agent)
    next_event_id = _event_id_sequence(last_event_id)

    async def events():
        yield "retry: 3000\n" + serialize_sse(
            watcher.ready_event(),
            next(next_event_id),
        )
        while not await request.is_disconnected():
            await asyncio.sleep(_SSE_CHECK_INTERVAL_SECONDS)
            emitted, should_close = watcher.poll()
            for event in emitted:
                yield serialize_sse(event, next(next_event_id))
            if should_close:
                break

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-store",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/agents/{agent_key}/authorize", response_model=ChatAuthorizeOut)
def authorize_agent(
    agent_key: str,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatAuthorizeOut:
    access_service = AgentAccessService(db)
    agent = access_service.get_granted_agent(user, agent_key)
    access_service.require_current_chat_membership(user, agent)
    credential_service = FeishuUserCredentialService(db)
    _ensure_chat_oauth_available(credential_service)
    return_to = build_chat_return_to(agent.agent_key)
    oauth_state = sign_chat_oauth_state(
        agent_key=agent.agent_key,
        user_id=user.id,
        return_to=return_to,
    )
    set_chat_oauth_state_cookie(response, oauth_state)
    return ChatAuthorizeOut(
        authorize_url=credential_service.oauth_client.build_authorize_url(oauth_state),
        return_to=return_to,
    )


@router.post(
    "/feishu/callback",
    response_model=ChatOAuthCallbackOut,
)
async def feishu_chat_callback(
    payload: ChatOAuthCallbackIn,
    request: Request,
    response: Response,
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    csrf_cookie: str | None = Cookie(default=None, alias="csrf_token"),
    oauth_state_cookie: str | None = Cookie(
        default=None,
        alias=CHAT_OAUTH_STATE_COOKIE,
    ),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatOAuthCallbackOut | JSONResponse:
    clear_chat_oauth_state_cookie(response)
    try:
        csrf_protect(
            request,
            x_csrf_token=x_csrf_token,
            csrf_cookie=csrf_cookie,
        )
    except HTTPException as exc:
        return _chat_oauth_error("csrf_rejected", exc.status_code)
    if not oauth_state_cookie or not hmac.compare_digest(
        payload.state,
        oauth_state_cookie,
    ):
        return _chat_oauth_error("oauth_state_mismatch", status.HTTP_400_BAD_REQUEST)
    try:
        oauth_state = verify_chat_oauth_state(payload.state)
    except ChatOAuthStateError:
        return _chat_oauth_error("oauth_state_invalid", status.HTTP_400_BAD_REQUEST)
    if oauth_state.user_id != user.id:
        return _chat_oauth_error("oauth_user_mismatch", status.HTTP_403_FORBIDDEN)

    credential_service = FeishuUserCredentialService(db)
    try:
        access_service = AgentAccessService(db)
        agent = access_service.get_granted_agent(user, oauth_state.agent_key)
        access_service.require_current_chat_membership(user, agent)
        credential_service.ensure_runtime_available()
        await credential_service.authorize_user(user, payload.code)
    except HTTPException as exc:
        error_code = (
            exc.detail.get("code")
            if isinstance(exc.detail, dict) and isinstance(exc.detail.get("code"), str)
            else "agent_access_changed"
        )
        return _chat_oauth_error(error_code, exc.status_code)
    except FeishuCredentialError as exc:
        error_status = _credential_error_status(exc)
        return _chat_oauth_error(exc.code, error_status)
    return ChatOAuthCallbackOut(
        agent_key=agent.agent_key,
        credential_status="active",
        return_to=oauth_state.return_to,
    )


@router.post(
    "/agents/{agent_key}/disconnect",
    response_model=ChatDisconnectOut,
    dependencies=[Depends(csrf_protect)],
)
def disconnect_agent(
    agent_key: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ChatDisconnectOut:
    AgentAccessService(db).get_granted_agent(user, agent_key)
    credential_status = FeishuUserCredentialService(db).disconnect(user)
    return ChatDisconnectOut(ok=True, credential_status=credential_status)


def _ensure_chat_oauth_available(service: FeishuUserCredentialService) -> None:
    try:
        service.ensure_runtime_available()
    except FeishuCredentialError as exc:
        raise HTTPException(
            status_code=_credential_error_status(exc),
            detail={"code": exc.code},
        ) from exc


def _credential_error_status(exc: FeishuCredentialError) -> int:
    if exc.code in {"chat_disabled", "chat_configuration_invalid"}:
        return status.HTTP_503_SERVICE_UNAVAILABLE
    if exc.code == "feishu_identity_mismatch":
        return status.HTTP_403_FORBIDDEN
    if exc.code in {
        "authorization_rejected",
        "required_scopes_missing",
        "token_expiry_invalid",
        "token_response_incomplete",
    }:
        return status.HTTP_400_BAD_REQUEST
    return status.HTTP_502_BAD_GATEWAY


def _chat_oauth_error(code: str, status_code: int) -> JSONResponse:
    error_response = JSONResponse(
        status_code=status_code,
        content={"detail": {"code": code}},
    )
    clear_chat_oauth_state_cookie(error_response)
    return error_response


def _event_id_sequence(last_event_id: str | None):
    previous = 0
    if last_event_id and last_event_id.isdecimal():
        previous = min(int(last_event_id), 9_223_372_036_854_775_000)
    current = max(previous + 1, int(time.time() * 1000))
    while True:
        yield str(current)
        current += 1
