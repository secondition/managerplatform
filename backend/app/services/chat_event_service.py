from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.models.agent import AiAgent
from app.models.user import User
from app.services.agent_access_service import AgentAccessService
from app.services.chat_projection_service import ChatProjectionService


@dataclass(frozen=True)
class ChatStreamEvent:
    event: str
    agent_key: str
    cursor_hint: str | None = None


class ChatEventWatcher:
    def __init__(
        self,
        db: Session,
        user: User,
        agent: AiAgent,
        *,
        runtime_settings: Settings = settings,
    ) -> None:
        self.db = db
        self.user = user
        self.agent = agent
        self.settings = runtime_settings
        self._snapshot = ChatProjectionService(
            db,
            runtime_settings=runtime_settings,
        ).snapshot(user, agent)
        self._last_runtime_state: tuple[str, str] | None = None

    def ready_event(self) -> ChatStreamEvent:
        return ChatStreamEvent(
            event="ready",
            agent_key=self.agent.agent_key,
            cursor_hint=_snapshot_hint(self._snapshot),
        )

    def poll(self) -> tuple[list[ChatStreamEvent], bool]:
        self.db.rollback()
        self.db.expire_all()
        access_service = AgentAccessService(
            self.db,
            runtime_settings=self.settings,
        )
        try:
            agent = access_service.get_granted_agent(
                self.user,
                self.agent.agent_key,
            )
        except HTTPException as exc:
            if exc.status_code == 404:
                return [self._event("agent.access_revoked")], True
            raise
        runtime = access_service.runtime_status(self.user, agent)
        if not runtime.can_read:
            if runtime.credential_status != "active":
                event_type = "authorization.required"
            elif runtime.membership_status != "active":
                event_type = "agent.access_revoked"
            else:
                event_type = "sync.delayed"
            return [self._event(event_type)], True

        events: list[ChatStreamEvent] = []
        runtime_state = (runtime.availability, runtime.sync_status)
        if runtime.availability == "sync_delayed" and runtime_state != self._last_runtime_state:
            events.append(self._event("sync.delayed"))
        self._last_runtime_state = runtime_state

        current = ChatProjectionService(
            self.db,
            runtime_settings=self.settings,
        ).snapshot(self.user, agent)
        hint = _snapshot_hint(current)
        old_ids = set(self._snapshot)
        current_ids = set(current)
        if current_ids - old_ids:
            events.append(self._event("message.created", hint))
        if old_ids - current_ids:
            events.append(self._event("message.deleted", hint))
        if any(
            self._snapshot[message_id] != current[message_id]
            for message_id in old_ids & current_ids
        ):
            events.append(self._event("message.updated", hint))
        self._snapshot = current
        if not events:
            events.append(self._event("heartbeat", hint))
        return events, False

    def _event(self, event: str, cursor_hint: str | None = None) -> ChatStreamEvent:
        return ChatStreamEvent(
            event=event,
            agent_key=self.agent.agent_key,
            cursor_hint=cursor_hint,
        )


def serialize_sse(event: ChatStreamEvent, event_id: str) -> str:
    payload = {
        "event": event.event,
        "agent_key": event.agent_key,
        "event_id": event_id,
    }
    if event.cursor_hint:
        payload["cursor_hint"] = event.cursor_hint
    data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    return f"id: {event_id}\nevent: {event.event}\ndata: {data}\n\n"


def _snapshot_hint(snapshot: dict[str, str]) -> str:
    raw = json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]
