from __future__ import annotations

import html
import hashlib
import unicodedata
import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.security import utcnow
from app.models.agent import AiAgent
from app.models.feishu_chat import (
    ChatSendRequest,
    FeishuChatMessage,
    FeishuChatSyncState,
)
from app.models.user import User
from app.services.agent_chat_config import (
    AgentChatConfig,
    legacy_agent_chat_config,
    resolve_agent_chat_config,
)
from app.services.chat_projection_service import ChatProjectionService
from app.services.feishu_user_credential_service import (
    FeishuCredentialError,
    FeishuUserCredentialService,
)
from app.services.feishu_user_message_client import (
    FeishuUserMessageClient,
    FeishuUserMessageError,
)


class ChatSendError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ChatSendResult:
    client_request_id: str
    status: str
    message_id: str | None
    error_code: str | None
    error_message: str | None


class ChatMessageSendService:
    def __init__(
        self,
        db: Session,
        *,
        runtime_settings: Settings = settings,
        credential_service: FeishuUserCredentialService | None = None,
        message_client: FeishuUserMessageClient | None = None,
    ) -> None:
        self.db = db
        self.settings = runtime_settings
        self.credential_service = credential_service or FeishuUserCredentialService(
            db,
            runtime_settings=runtime_settings,
        )
        self.message_client = message_client or FeishuUserMessageClient(runtime_settings)

    async def send(
        self,
        user: User,
        agent: AiAgent,
        *,
        text: str,
        client_request_id: str,
    ) -> ChatSendResult:
        normalized = self.validate_text(text)
        text_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        existing = self._get_request(user.id, agent.id, client_request_id)
        if existing is not None and existing.request_text_hash != text_hash:
            raise ChatSendError("idempotency_key_conflict")
        if existing is not None and existing.status == "sent_to_feishu":
            return self._serialize(existing, user, agent)

        request = existing or ChatSendRequest(
            user_id=user.id,
            agent_id=agent.id,
            client_request_id=client_request_id,
            feishu_uuid=str(uuid.uuid4()),
            request_text_hash=text_hash,
            created_by=user.id,
            updated_by=user.id,
        )
        request.status = "sending"
        request.error_code = None
        request.error_message = None
        if existing is None:
            self.db.add(request)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            concurrent = self._get_request(user.id, agent.id, client_request_id)
            if concurrent is None:
                raise
            if concurrent.request_text_hash != text_hash:
                raise ChatSendError("idempotency_key_conflict")
            return self._serialize(concurrent, user, agent)

        chat_config = resolve_agent_chat_config(agent, self.settings)
        if not (
            chat_config.target_chat_id
            and chat_config.agent_mention_id
            and chat_config.agent_display_name
        ):
            return self._mark_failed(request.id, "chat_configuration_invalid")
        try:
            access_token = await self.credential_service.get_valid_access_token(user.id)
            message_id = await self.message_client.send_text(
                access_token=access_token,
                chat_id=chat_config.target_chat_id,
                text=self.build_feishu_text(normalized, chat_config),
                request_uuid=request.feishu_uuid,
            )
        except FeishuCredentialError as exc:
            return self._mark_failed(request.id, _credential_error_code(exc))
        except FeishuUserMessageError as exc:
            return self._mark_failed(request.id, exc.code)
        finally:
            await self.message_client.aclose()

        request = self.db.get(ChatSendRequest, request.id)
        if request is None:
            raise RuntimeError("Chat send request disappeared")
        request.status = "sent_to_feishu"
        request.feishu_message_id = message_id
        request.error_code = None
        request.error_message = None
        request.updated_by = user.id
        self._request_immediate_sync(agent.id, chat_config.target_chat_id)
        self.db.commit()
        return self._serialize(request, user, agent)

    def validate_text(self, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            raise ChatSendError("message_empty")
        if len(normalized) > self.settings.feishu_chat_send_text_max_length:
            raise ChatSendError("message_too_long")
        if any(_is_unsafe_control(character) for character in normalized):
            raise ChatSendError("message_contains_control_characters")
        return normalized

    def build_feishu_text(
        self,
        text: str,
        chat_config: AgentChatConfig | None = None,
    ) -> str:
        resolved = chat_config or legacy_agent_chat_config(self.settings)
        mention_id = resolved.agent_mention_id
        display_name = resolved.agent_display_name
        if not mention_id or not display_name:
            raise ChatSendError("chat_configuration_invalid")
        safe_mention_id = html.escape(mention_id, quote=True)
        safe_display_name = html.escape(display_name, quote=False)
        safe_text = html.escape(text, quote=False)
        return f'<at user_id="{safe_mention_id}">{safe_display_name}</at> {safe_text}'

    def _get_request(
        self,
        user_id: int,
        agent_id: int,
        client_request_id: str,
    ) -> ChatSendRequest | None:
        return self.db.scalar(
            select(ChatSendRequest).where(
                ChatSendRequest.user_id == user_id,
                ChatSendRequest.agent_id == agent_id,
                ChatSendRequest.client_request_id == client_request_id,
                ChatSendRequest.deleted_at.is_(None),
            )
        )

    def _mark_failed(self, request_id: int, error_code: str) -> ChatSendResult:
        request = self.db.get(ChatSendRequest, request_id)
        if request is None:
            raise RuntimeError("Chat send request disappeared")
        request.status = "failed"
        request.error_code = error_code
        request.error_message = _safe_error_message(error_code)
        self.db.commit()
        return ChatSendResult(
            client_request_id=request.client_request_id,
            status="failed",
            message_id=None,
            error_code=error_code,
            error_message=request.error_message,
        )

    def _serialize(
        self,
        request: ChatSendRequest,
        user: User,
        agent: AiAgent,
    ) -> ChatSendResult:
        public_message_id = None
        response_status = request.status
        if request.feishu_message_id:
            message = self.db.scalar(
                select(FeishuChatMessage).where(
                    FeishuChatMessage.message_id == request.feishu_message_id
                )
            )
            if message is not None:
                public_message_id = ChatProjectionService(
                    self.db,
                    runtime_settings=self.settings,
                ).public_message_id(user, agent, message)
                response_status = "synced"
        return ChatSendResult(
            client_request_id=request.client_request_id,
            status=response_status,
            message_id=public_message_id,
            error_code=request.error_code,
            error_message=request.error_message,
        )

    def _request_immediate_sync(self, agent_id: int, chat_id: str) -> None:
        state = self.db.scalar(
            select(FeishuChatSyncState).where(
                FeishuChatSyncState.agent_id == agent_id,
                FeishuChatSyncState.chat_id == chat_id,
                FeishuChatSyncState.deleted_at.is_(None),
            )
        )
        if state is not None:
            state.next_sync_at = utcnow()


def _is_unsafe_control(character: str) -> bool:
    if character in {"\n", "\t"}:
        return False
    category = unicodedata.category(character)
    return category in {"Cc", "Cf"}


def _credential_error_code(error: FeishuCredentialError) -> str:
    if error.code in {
        "authorization_required",
        "credential_refresh_in_progress",
        "chat_disabled",
        "chat_configuration_invalid",
    }:
        return error.code
    return "authorization_required" if not error.retryable else "credential_unavailable"


def _safe_error_message(error_code: str) -> str:
    messages = {
        "authorization_required": "飞书授权已失效，请重新授权后发送。",
        "credential_refresh_in_progress": "飞书授权正在刷新，请稍后重试。",
        "credential_unavailable": "暂时无法获取飞书授权，请稍后重试。",
        "chat_disabled": "聊天服务当前未启用。",
        "chat_configuration_invalid": "聊天服务配置不完整。",
        "send_network_error": "暂时无法连接飞书，请使用同一请求重试。",
        "send_rate_limited": "发送过于频繁，请稍后使用同一请求重试。",
        "send_service_unavailable": "飞书服务暂时不可用，请稍后重试。",
        "send_rejected": "飞书未接受该消息，请重新授权或稍后重试。",
        "send_response_incomplete": "发送结果暂未确认，请使用同一请求重试。",
        "send_response_invalid": "发送结果暂未确认，请使用同一请求重试。",
    }
    return messages.get(error_code, "消息发送失败，请稍后重试。")
