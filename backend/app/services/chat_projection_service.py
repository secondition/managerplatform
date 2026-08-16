from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import PurePath
from typing import Any

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.models.agent import AiAgent
from app.models.feishu_chat import FeishuChatMessage
from app.models.user import User
from app.services.agent_chat_config import resolve_agent_chat_config


class ChatProjectionError(ValueError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ProjectedMessage:
    source: FeishuChatMessage
    payload: dict[str, Any]


@dataclass(frozen=True)
class ChatMessagePage:
    items: tuple[dict[str, Any], ...]
    next_cursor: str | None
    has_more: bool


class ChatProjectionService:
    def __init__(
        self,
        db: Session,
        *,
        runtime_settings: Settings = settings,
    ) -> None:
        self.db = db
        self.settings = runtime_settings

    def list_messages(
        self,
        user: User,
        agent: AiAgent,
        *,
        cursor: str | None = None,
        limit: int = 50,
    ) -> ChatMessagePage:
        records = self.project_messages(user, agent)
        if cursor:
            cursor_time, cursor_row_id = self._decode_cursor(cursor, user, agent)
            records = [
                record
                for record in records
                if (record.source.create_time_ms, record.source.id)
                < (cursor_time, cursor_row_id)
            ]
        has_more = len(records) > limit
        selected = records[-limit:]
        next_cursor = None
        if has_more and selected:
            first = selected[0].source
            next_cursor = self._encode_cursor(
                user,
                agent,
                first.create_time_ms,
                first.id,
            )
        return ChatMessagePage(
            items=tuple(record.payload for record in selected),
            next_cursor=next_cursor,
            has_more=has_more,
        )

    def project_messages(
        self,
        user: User,
        agent: AiAgent,
    ) -> list[ProjectedMessage]:
        chat_config = resolve_agent_chat_config(agent, self.settings)
        chat_id = chat_config.target_chat_id
        rows = list(
            self.db.scalars(
                select(FeishuChatMessage)
                .where(FeishuChatMessage.chat_id == chat_id)
                .order_by(
                    FeishuChatMessage.create_time_ms,
                    FeishuChatMessage.id,
                )
            ).all()
        )
        rows_by_message_id = {row.message_id: row for row in rows}
        roots = {
            row.message_id: row
            for row in rows
            if self._is_user_root(row, user, chat_config.agent_mention_id)
        }
        records: list[ProjectedMessage] = []
        for row in rows:
            if row.message_id in roots:
                payload = self._project_user_message(
                    row,
                    user,
                    agent,
                    chat_config.agent_mention_id,
                )
            elif self._is_agent_reply(
                row,
                roots,
                rows_by_message_id,
                chat_config.agent_sender_id,
            ):
                payload = self._project_agent_message(row, user, agent)
            else:
                payload = None
            if payload is not None:
                records.append(ProjectedMessage(source=row, payload=payload))
        return records

    def get_owned_file_message(
        self,
        user: User,
        agent: AiAgent,
        public_message_id: str,
    ) -> FeishuChatMessage:
        record = next(
            (
                item
                for item in self.project_messages(user, agent)
                if hmac.compare_digest(
                    self.public_message_id(user, agent, item.source),
                    public_message_id,
                )
                and item.source.msg_type == "file"
                and item.payload.get("kind") == "assistant_file"
            ),
            None,
        )
        if record is None:
            raise ChatProjectionError("attachment_not_found")
        file_key = _content_string(record.source.content_json, "file_key")
        if not file_key:
            raise ChatProjectionError("attachment_unavailable")
        return record.source

    def public_message_id(
        self,
        user: User,
        agent: AiAgent,
        row: FeishuChatMessage,
    ) -> str:
        raw = f"1:{user.id}:{agent.id}:{row.id}".encode("ascii")
        digest = hmac.digest(self._signing_key(), raw, "sha256").hex()
        return f"msg_{digest}"

    def snapshot(self, user: User, agent: AiAgent) -> dict[str, str]:
        snapshot: dict[str, str] = {}
        for record in self.project_messages(user, agent):
            public_id = str(record.payload["id"])
            serialized = json.dumps(
                record.payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            snapshot[public_id] = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
        return snapshot

    def _is_user_root(
        self,
        row: FeishuChatMessage,
        user: User,
        mention_id: str,
    ) -> bool:
        if (
            row.deleted
            or row.msg_type != "text"
            or row.sender_type != "user"
            or row.sender_id != user.feishu_open_id
        ):
            return False
        if not mention_id or not isinstance(row.mentions_json, list):
            return False
        return any(
            isinstance(mention, dict)
            and _optional_string(mention.get("id")) == mention_id
            for mention in row.mentions_json
        )

    def _is_agent_reply(
        self,
        row: FeishuChatMessage,
        roots: dict[str, FeishuChatMessage],
        rows_by_message_id: dict[str, FeishuChatMessage],
        agent_sender_id: str,
    ) -> bool:
        if (
            row.deleted
            or row.sender_id != agent_sender_id
        ):
            return False
        pending = [row.parent_id, row.root_id]
        visited: set[str] = {row.message_id}
        while pending:
            message_id = pending.pop()
            if not message_id or message_id in visited:
                continue
            if message_id in roots:
                return True
            visited.add(message_id)
            ancestor = rows_by_message_id.get(message_id)
            if ancestor is not None:
                pending.extend((ancestor.parent_id, ancestor.root_id))
        return False

    def _project_user_message(
        self,
        row: FeishuChatMessage,
        user: User,
        agent: AiAgent,
        mention_id: str,
    ) -> dict[str, Any] | None:
        text = _content_string(row.content_json, "text")
        if text is None:
            return None
        for mention in row.mentions_json or []:
            if not isinstance(mention, dict):
                continue
            if _optional_string(mention.get("id")) != mention_id:
                continue
            key = _optional_string(mention.get("key"))
            if key:
                text = text.replace(key, "")
        normalized = text.strip()
        if not normalized:
            return None
        return {
            "id": self.public_message_id(user, agent, row),
            "role": "user",
            "kind": "user_text",
            "body_text": normalized,
            "created_at": _message_datetime(row.create_time_ms),
        }

    def _project_agent_message(
        self,
        row: FeishuChatMessage,
        user: User,
        agent: AiAgent,
    ) -> dict[str, Any] | None:
        base = {
            "id": self.public_message_id(user, agent, row),
            "role": "assistant",
            "created_at": _message_datetime(row.create_time_ms),
        }
        if row.msg_type == "text":
            body = _content_string(row.content_json, "text")
            if body is None or not body.strip():
                return None
            return {
                **base,
                "kind": "assistant_markdown",
                "body_markdown": body,
            }
        if row.msg_type == "file":
            file_key = _content_string(row.content_json, "file_key")
            file_name = display_file_name(row.content_json)
            public_id = str(base["id"])
            return {
                **base,
                "kind": "assistant_file",
                "file_name": file_name,
                "file_type": _file_type(file_name),
                "file_size": None,
                "download_status": "available" if file_key else "unavailable",
                "download_url": (
                    f"/api/v1/chat/agents/{agent.agent_key}/messages/"
                    f"{public_id}/attachment"
                    if file_key
                    else None
                ),
            }
        return {
            **base,
            "kind": "unsupported",
            "label": "暂不支持的消息类型",
        }

    def _encode_cursor(
        self,
        user: User,
        agent: AiAgent,
        create_time_ms: int,
        row_id: int,
    ) -> str:
        raw = json.dumps(
            [1, user.id, agent.id, create_time_ms, row_id],
            separators=(",", ":"),
        ).encode("ascii")
        return f"cur_{self._cursor_cipher().encrypt(raw).decode('ascii')}"

    def _decode_cursor(
        self,
        cursor: str,
        user: User,
        agent: AiAgent,
    ) -> tuple[int, int]:
        if not cursor.startswith("cur_"):
            raise ChatProjectionError("invalid_cursor")
        try:
            raw = self._cursor_cipher().decrypt(cursor[4:].encode("ascii"))
            payload = json.loads(raw.decode("ascii"))
        except (InvalidToken, UnicodeError, ValueError, json.JSONDecodeError):
            raise ChatProjectionError("invalid_cursor") from None
        if (
            not isinstance(payload, list)
            or
            len(payload) != 5
            or payload[:3] != [1, user.id, agent.id]
            or not all(isinstance(item, int) for item in payload[3:])
        ):
            raise ChatProjectionError("invalid_cursor")
        return payload[3], payload[4]

    def _cursor_cipher(self) -> Fernet:
        key = base64.urlsafe_b64encode(
            hmac.digest(
                self._signing_key(),
                b"feishu-chat-cursor-encryption-v1",
                "sha256",
            )
        )
        return Fernet(key)

    def _signing_key(self) -> bytes:
        return hmac.digest(
            self.settings.jwt_secret.encode("utf-8"),
            b"feishu-chat-public-reference-v1",
            "sha256",
        )


def _content_string(content: dict | list | None, key: str) -> str | None:
    if not isinstance(content, dict):
        return None
    return _optional_string(content.get(key))


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _message_datetime(create_time_ms: int) -> datetime:
    return datetime.fromtimestamp(create_time_ms / 1000, tz=timezone.utc)


def display_file_name(content: dict | list | None) -> str:
    raw_name = (
        _content_string(content, "file_name")
        or _content_string(content, "name")
        or "查宝生成的文件"
    )
    base_name = re.split(r"[\\/]", raw_name)[-1]
    cleaned = "".join(
        character
        for character in base_name
        if character not in "\r\n\0<>:\"|?*" and ord(character) >= 32
    ).strip()
    return cleaned[:180] or "查宝生成的文件"


def _file_type(file_name: str) -> str | None:
    suffix = PurePath(file_name).suffix.lower().lstrip(".")
    return suffix if re.fullmatch(r"[a-z0-9]{1,10}", suffix) else None
