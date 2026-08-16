from __future__ import annotations

import re
from dataclasses import dataclass
from typing import AsyncIterator

import httpx
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.models.agent import AiAgent
from app.models.user import User
from app.services.chat_projection_service import (
    ChatProjectionError,
    ChatProjectionService,
    display_file_name,
)
from app.services.feishu_tenant_client import FeishuTenantClient, FeishuTenantError


class ChatAttachmentError(RuntimeError):
    def __init__(self, code: str, *, status_code: int) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code


@dataclass
class ChatAttachmentDownload:
    response: httpx.Response
    tenant_client: FeishuTenantClient
    file_name: str
    content_type: str
    content_length: int
    max_bytes: int

    async def iter_bytes(self) -> AsyncIterator[bytes]:
        streamed_bytes = 0
        try:
            async for chunk in self.response.aiter_bytes(65_536):
                if chunk:
                    streamed_bytes += len(chunk)
                    if streamed_bytes > self.max_bytes:
                        raise ChatAttachmentError(
                            "attachment_too_large",
                            status_code=413,
                        )
                    yield chunk
        finally:
            await self.aclose()

    async def aclose(self) -> None:
        await self.response.aclose()
        await self.tenant_client.aclose()


class ChatAttachmentService:
    def __init__(
        self,
        db: Session,
        *,
        runtime_settings: Settings = settings,
        tenant_client: FeishuTenantClient | None = None,
    ) -> None:
        self.db = db
        self.settings = runtime_settings
        self.tenant_client = tenant_client or FeishuTenantClient(runtime_settings)

    async def open_download(
        self,
        user: User,
        agent: AiAgent,
        public_message_id: str,
    ) -> ChatAttachmentDownload:
        try:
            message = ChatProjectionService(
                self.db,
                runtime_settings=self.settings,
            ).get_owned_file_message(user, agent, public_message_id)
        except ChatProjectionError as exc:
            raise ChatAttachmentError(exc.code, status_code=404) from exc
        content = message.content_json if isinstance(message.content_json, dict) else {}
        file_key = content.get("file_key")
        if not isinstance(file_key, str) or not file_key:
            raise ChatAttachmentError("attachment_unavailable", status_code=404)
        try:
            response = await self.tenant_client.open_message_resource(
                message.message_id,
                file_key,
            )
        except FeishuTenantError as exc:
            await self.tenant_client.aclose()
            status_code = 503 if exc.retryable else 404
            raise ChatAttachmentError(
                "attachment_temporarily_unavailable"
                if exc.retryable
                else "attachment_unavailable",
                status_code=status_code,
            ) from exc

        content_length = _content_length(response)
        if content_length is None:
            await response.aclose()
            await self.tenant_client.aclose()
            raise ChatAttachmentError("attachment_size_unknown", status_code=502)
        if content_length > self.settings.feishu_chat_attachment_max_bytes:
            await response.aclose()
            await self.tenant_client.aclose()
            raise ChatAttachmentError("attachment_too_large", status_code=413)
        return ChatAttachmentDownload(
            response=response,
            tenant_client=self.tenant_client,
            file_name=display_file_name(message.content_json),
            content_type=_content_type(response),
            content_length=content_length,
            max_bytes=self.settings.feishu_chat_attachment_max_bytes,
        )


def _content_length(response: httpx.Response) -> int | None:
    raw = response.headers.get("content-length")
    if raw is None:
        return None
    try:
        parsed = int(raw)
    except (TypeError, ValueError, OverflowError):
        return None
    return parsed if parsed >= 0 else None


def _content_type(response: httpx.Response) -> str:
    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
    if re.fullmatch(r"[a-z0-9!#$&^_.+-]+/[a-z0-9!#$&^_.+-]+", media_type):
        return media_type
    return "application/octet-stream"
