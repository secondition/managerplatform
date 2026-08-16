from __future__ import annotations

import json
import random
import calendar
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.security import utcnow
from app.models.agent import AiAgent
from app.models.feishu_chat import (
    FeishuChatMember,
    FeishuChatMessage,
    FeishuChatSyncState,
)
from app.services.agent_chat_config import resolve_agent_chat_config
from app.services.feishu_tenant_client import (
    FeishuPage,
    FeishuTenantClient,
    FeishuTenantError,
)

MESSAGE_OVERLAP_MS = 2_000
MAX_BACKOFF_SECONDS = 300
BLOCKED_RETRY_SECONDS = 300


@dataclass(frozen=True)
class ChatSyncResult:
    message_count: int = 0
    member_count: int = 0
    message_pages: int = 0
    member_pages: int = 0
    status: str = "healthy"


class FeishuChatSyncService:
    def __init__(
        self,
        db: Session,
        *,
        runtime_settings: Settings = settings,
        tenant_client: FeishuTenantClient | None = None,
        random_source: random.Random | None = None,
    ) -> None:
        self.db = db
        self.settings = runtime_settings
        self.tenant_client = tenant_client or FeishuTenantClient(runtime_settings)
        self.random = random_source or random.Random()

    def ensure_sync_state(self) -> FeishuChatSyncState:
        agent = self._agent()
        chat_id = resolve_agent_chat_config(agent, self.settings).target_chat_id
        if not chat_id:
            raise FeishuTenantError("chat_configuration_invalid", retryable=False)
        state = self.db.scalar(
            select(FeishuChatSyncState).where(
                FeishuChatSyncState.agent_id == agent.id,
                FeishuChatSyncState.chat_id == chat_id,
                FeishuChatSyncState.deleted_at.is_(None),
            )
        )
        if state is not None:
            return state
        now = utcnow()
        state = FeishuChatSyncState(
            agent_id=agent.id,
            chat_id=chat_id,
            status="backfilling",
            sync_mode="backfill",
            backfill_start_time_ms=_epoch_ms(
                now - timedelta(days=self.settings.feishu_chat_initial_backfill_days)
            ),
            next_sync_at=now,
        )
        self.db.add(state)
        self.db.commit()
        self.db.refresh(state)
        return state

    async def sync_due(self) -> ChatSyncResult:
        state = self.ensure_sync_state()
        now = utcnow()
        if state.status == "blocked" and (
            state.next_sync_at is None or state.next_sync_at > now
        ):
            return ChatSyncResult(status="blocked")
        if state.rate_limited_until and state.rate_limited_until > now:
            return ChatSyncResult(status="rate_limited")
        if state.next_sync_at and state.next_sync_at > now:
            return ChatSyncResult(status=state.status)

        message_count = 0
        member_count = 0
        message_pages = 0
        member_pages = 0
        state_id = state.id
        try:
            member_sync_due = self._member_sync_due(state, now)
            if state.last_success_at is None or member_sync_due:
                await self._verify_target_chat(state)
            if member_sync_due:
                member_count, member_pages = await self.sync_members(state)
            message_count, message_pages = await self.sync_messages(state)
            self.cleanup_expired_messages()
            return ChatSyncResult(
                message_count=message_count,
                member_count=member_count,
                message_pages=message_pages,
                member_pages=member_pages,
                status=state.status,
            )
        except FeishuTenantError as exc:
            self.db.rollback()
            self._record_failure(state_id, exc)
            raise
        except Exception:
            self.db.rollback()
            sanitized_error = FeishuTenantError(
                "sync_internal_error",
                retryable=True,
            )
            self._record_failure(
                state_id,
                sanitized_error,
            )
            raise sanitized_error from None

    async def sync_members(
        self,
        state: FeishuChatSyncState | None = None,
    ) -> tuple[int, int]:
        sync_state = state or self.ensure_sync_state()
        snapshot_at = utcnow()
        page_token: str | None = None
        members: dict[tuple[str, str], dict[str, Any]] = {}
        pages = 0
        while True:
            page = await self.tenant_client.list_chat_members_page(
                sync_state.chat_id,
                page_token=page_token,
            )
            pages += 1
            self._collect_members(page, members)
            if not page.has_more:
                break
            page_token = page.page_token

        existing = {
            (row.member_id, row.member_id_type): row
            for row in self.db.scalars(
                select(FeishuChatMember).where(
                    FeishuChatMember.chat_id == sync_state.chat_id,
                    FeishuChatMember.deleted_at.is_(None),
                )
            ).all()
        }
        for identity, item in members.items():
            row = existing.get(identity)
            if row is None:
                row = FeishuChatMember(
                    chat_id=sync_state.chat_id,
                    member_id=identity[0],
                    member_id_type=identity[1],
                    last_seen_at=snapshot_at,
                    synced_at=snapshot_at,
                )
                self.db.add(row)
            row.name = _optional_string(item.get("name"))
            row.member_type = _optional_string(item.get("member_type"))
            row.is_active = True
            row.last_seen_at = snapshot_at
            row.synced_at = snapshot_at
        for identity, row in existing.items():
            if identity not in members:
                row.is_active = False
                row.synced_at = snapshot_at

        sync_state.last_member_sync_at = snapshot_at
        self.db.commit()
        return len(members), pages

    async def sync_messages(
        self,
        state: FeishuChatSyncState | None = None,
    ) -> tuple[int, int]:
        sync_state = state or self.ensure_sync_state()
        now = utcnow()
        if sync_state.current_window_start_time_ms is None:
            if sync_state.sync_mode == "backfill":
                sync_state.current_window_start_time_ms = (
                    sync_state.backfill_start_time_ms
                    or _epoch_ms(
                        now
                        - timedelta(
                            days=self.settings.feishu_chat_initial_backfill_days
                        )
                    )
                )
            else:
                sync_state.current_window_start_time_ms = max(
                    0,
                    (sync_state.last_message_create_time_ms or _epoch_ms(now))
                    - MESSAGE_OVERLAP_MS,
                )
        if sync_state.current_window_end_time_ms is None:
            sync_state.current_window_end_time_ms = _epoch_ms(now)
        self.db.commit()

        processed = 0
        pages = 0
        max_create_time = sync_state.last_message_create_time_ms
        page_token = sync_state.last_page_token
        while True:
            page = await self.tenant_client.list_chat_messages_page(
                sync_state.chat_id,
                start_time_ms=sync_state.current_window_start_time_ms,
                end_time_ms=sync_state.current_window_end_time_ms,
                page_token=page_token,
            )
            pages += 1
            synced_at = utcnow()
            for item in page.items:
                message = self._upsert_message(sync_state.chat_id, item, synced_at)
                if message is None:
                    continue
                processed += 1
                max_create_time = max(max_create_time or 0, message.create_time_ms)

            if page.has_more:
                sync_state.last_page_token = page.page_token
                if max_create_time:
                    sync_state.last_message_create_time_ms = max_create_time
                self.db.commit()
                page_token = page.page_token
                continue

            finished_at = utcnow()
            sync_state.last_page_token = None
            sync_state.last_message_create_time_ms = (
                max_create_time or sync_state.current_window_end_time_ms
            )
            sync_state.last_success_at = finished_at
            sync_state.last_message_sync_at = finished_at
            sync_state.current_window_start_time_ms = None
            sync_state.current_window_end_time_ms = None
            sync_state.sync_mode = "incremental"
            sync_state.status = "healthy"
            sync_state.next_sync_at = finished_at + timedelta(
                seconds=self.settings.feishu_chat_sync_interval_seconds
            )
            sync_state.rate_limited_until = None
            sync_state.consecutive_failures = 0
            sync_state.last_error = None
            self.db.commit()
            return processed, pages

    def cleanup_expired_messages(self) -> int:
        cutoff_ms = _epoch_ms(
            utcnow() - timedelta(days=self.settings.feishu_chat_cache_retention_days)
        )
        result = self.db.execute(
            delete(FeishuChatMessage).where(
                FeishuChatMessage.create_time_ms < cutoff_ms
            )
        )
        self.db.commit()
        return result.rowcount or 0

    async def _verify_target_chat(self, state: FeishuChatSyncState) -> None:
        agent = self.db.get(AiAgent, state.agent_id)
        if agent is None:
            raise FeishuTenantError("chat_configuration_invalid", retryable=False)
        expected_name = resolve_agent_chat_config(
            agent,
            self.settings,
        ).target_chat_name
        chat = await self.tenant_client.get_chat(state.chat_id)
        if not expected_name or _optional_string(chat.get("name")) != expected_name:
            raise FeishuTenantError("target_chat_mismatch", retryable=False)
        if _optional_string(chat.get("chat_status")) not in {None, "normal"}:
            raise FeishuTenantError("target_chat_unavailable", retryable=False)

    def _member_sync_due(self, state: FeishuChatSyncState, now) -> bool:
        return (
            state.last_member_sync_at is None
            or state.last_member_sync_at
            + timedelta(seconds=self.settings.feishu_chat_member_sync_interval_seconds)
            <= now
        )

    def _collect_members(
        self,
        page: FeishuPage,
        members: dict[tuple[str, str], dict[str, Any]],
    ) -> None:
        for item in page.items:
            member_id = _optional_string(item.get("member_id"))
            member_id_type = _optional_string(item.get("member_id_type")) or "open_id"
            if not member_id or member_id_type != "open_id":
                continue
            members[(member_id, member_id_type)] = item

    def _upsert_message(
        self,
        chat_id: str,
        item: dict[str, Any],
        synced_at,
    ) -> FeishuChatMessage | None:
        message_id = _optional_string(item.get("message_id"))
        create_time_ms = _milliseconds(item.get("create_time"))
        msg_type = _optional_string(item.get("msg_type"))
        if not message_id or create_time_ms is None or not msg_type:
            return None
        row = self.db.scalar(
            select(FeishuChatMessage).where(
                FeishuChatMessage.message_id == message_id
            )
        )
        if row is None:
            row = FeishuChatMessage(
                message_id=message_id,
                chat_id=chat_id,
                msg_type=msg_type,
                create_time_ms=create_time_ms,
                synced_at=synced_at,
            )
            self.db.add(row)
        sender = item.get("sender") if isinstance(item.get("sender"), dict) else {}
        row.chat_id = chat_id
        row.sender_id = _optional_string(sender.get("id")) or _optional_string(
            sender.get("sender_id")
        )
        row.sender_id_type = _optional_string(sender.get("id_type"))
        row.sender_type = _optional_string(sender.get("sender_type"))
        row.msg_type = msg_type
        row.content_json = _content_json(item.get("body"))
        row.mentions_json = _mentions_json(item.get("mentions"))
        row.parent_id = _optional_string(item.get("parent_id"))
        row.root_id = _optional_string(item.get("root_id"))
        row.thread_id = _optional_string(item.get("thread_id"))
        row.create_time_ms = create_time_ms
        row.update_time_ms = _milliseconds(item.get("update_time"))
        row.deleted = _boolean(item.get("deleted"))
        row.updated = _boolean(item.get("updated"))
        row.synced_at = synced_at
        return row

    def _record_failure(self, state_id: int, error: FeishuTenantError) -> None:
        state = self.db.get(FeishuChatSyncState, state_id)
        if state is None:
            return
        now = utcnow()
        state.consecutive_failures += 1
        state.last_error = _safe_error_summary(error)
        if not error.retryable:
            state.status = "blocked"
            state.next_sync_at = now + timedelta(seconds=BLOCKED_RETRY_SECONDS)
            state.rate_limited_until = None
        else:
            delay_seconds = error.retry_after_seconds or self._backoff_seconds(
                state.consecutive_failures
            )
            retry_at = now + timedelta(seconds=delay_seconds)
            state.next_sync_at = retry_at
            if error.rate_limited:
                state.status = "rate_limited"
                state.rate_limited_until = retry_at
            else:
                state.status = "delayed"
                state.rate_limited_until = None
        self.db.commit()

    def _backoff_seconds(self, failures: int) -> int:
        base = min(MAX_BACKOFF_SECONDS, 2 ** min(max(failures, 1), 8))
        return min(MAX_BACKOFF_SECONDS, base + self.random.randint(0, max(1, base // 4)))

    def _agent(self) -> AiAgent:
        agent = self.db.scalar(
            select(AiAgent).where(
                AiAgent.agent_key == "chabao",
                AiAgent.implementation_type == "feishu_group_projection",
                AiAgent.enabled.is_(True),
                AiAgent.deleted_at.is_(None),
            )
        )
        if agent is None:
            raise RuntimeError("Enabled Feishu chat agent is not configured")
        return agent


def _safe_error_summary(error: FeishuTenantError) -> str:
    if error.log_id:
        return f"{error.category}; log_id={error.log_id}"
    return error.category


def _epoch_ms(value) -> int:
    return calendar.timegm(value.utctimetuple()) * 1000 + value.microsecond // 1000


def _milliseconds(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if parsed <= 0:
        return None
    return parsed * 1000 if parsed < 10_000_000_000 else parsed


def _boolean(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return bool(value)


def _optional_string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _content_json(body: Any) -> dict | list | None:
    if not isinstance(body, dict):
        return None
    raw_content = body.get("content")
    if not isinstance(raw_content, str) or not raw_content:
        return None
    try:
        parsed = json.loads(raw_content)
    except ValueError:
        return {"text": raw_content}
    return parsed if isinstance(parsed, (dict, list)) else None


def _mentions_json(value: Any) -> list | None:
    if not isinstance(value, list):
        return None
    result: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        sanitized = {
            key: item[key]
            for key in ("key", "id", "id_type", "name", "tenant_key")
            if isinstance(item.get(key), str)
        }
        if sanitized:
            result.append(sanitized)
    return result or None
