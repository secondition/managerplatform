from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings, settings
from app.core.security import utcnow
from app.models.agent import AiAgent, AiAgentGroupGrant, AiAgentUserGrant
from app.models.feishu_chat import (
    FeishuChatMember,
    FeishuChatSyncState,
    FeishuUserCredential,
)
from app.models.org import Group, GroupMember
from app.models.user import User
from app.services.feishu_user_oauth_client import missing_required_chat_scopes
from app.services.agent_chat_config import (
    AgentChatConfig,
    resolve_agent_chat_config,
    store_agent_chat_config,
)
from app.utils.image_upload import delete_managed_upload, validate_raster_image


AGENT_AVATAR_UPLOAD_DIR = (
    Path(__file__).resolve().parents[2] / "storage" / "uploads" / "agents"
)
AGENT_AVATAR_URL_PREFIX = "/uploads/agents/"
MAX_AGENT_AVATAR_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class AgentRuntimeStatus:
    availability: str
    credential_status: str
    membership_status: str
    sync_status: str
    can_read: bool
    can_send: bool
    blocked_reason: str | None
    last_sync_at: datetime | None
    sync_delay_seconds: int | None


class AgentAccessService:
    def __init__(
        self,
        db: Session,
        *,
        runtime_settings: Settings = settings,
    ) -> None:
        self.db = db
        self.settings = runtime_settings

    def list_platform_granted_agents(self, user: User) -> list[AiAgent]:
        if user.status != "active" or user.deleted_at is not None:
            return []
        direct_agent_ids = select(AiAgentUserGrant.agent_id).where(
            AiAgentUserGrant.user_id == user.id,
            AiAgentUserGrant.deleted_at.is_(None),
        )
        group_agent_ids = (
            select(AiAgentGroupGrant.agent_id)
            .join(
                Group,
                Group.id == AiAgentGroupGrant.group_id,
            )
            .join(
                GroupMember,
                GroupMember.group_id == AiAgentGroupGrant.group_id,
            )
            .where(
                GroupMember.user_id == user.id,
                GroupMember.deleted_at.is_(None),
                Group.deleted_at.is_(None),
                AiAgentGroupGrant.deleted_at.is_(None),
            )
        )
        return list(
            self.db.scalars(
                select(AiAgent)
                .where(
                    AiAgent.deleted_at.is_(None),
                    AiAgent.enabled.is_(True),
                    or_(
                        AiAgent.id.in_(direct_agent_ids),
                        AiAgent.id.in_(group_agent_ids),
                    ),
                )
                .order_by(AiAgent.sort_order, AiAgent.id)
            ).all()
        )

    def has_platform_grant(self, user: User, agent: AiAgent) -> bool:
        return any(
            item.id == agent.id for item in self.list_platform_granted_agents(user)
        )

    def get_granted_agent(self, user: User, agent_key: str) -> AiAgent:
        normalized_key = agent_key.strip()
        agent = next(
            (
                item
                for item in self.list_platform_granted_agents(user)
                if item.agent_key == normalized_key
            ),
            None,
        )
        if agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return agent

    def require_current_chat_membership(self, user: User, agent: AiAgent) -> None:
        runtime = self.runtime_status(user, agent)
        if runtime.membership_status == "active":
            return
        reason_by_status = {
            "unknown": "membership_not_synchronized",
            "stale": "membership_snapshot_stale",
            "not_member": "not_chat_member",
        }
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": reason_by_status.get(
                    runtime.membership_status,
                    "membership_not_synchronized",
                )
            },
        )

    def runtime_status(self, user: User, agent: AiAgent) -> AgentRuntimeStatus:
        credential_status = self._credential_status(user.id)
        sync_state = self._sync_state(agent)
        membership_status = self._membership_status(user, sync_state)
        sync_status = self._sync_status(sync_state)
        last_sync_at = sync_state.last_message_sync_at if sync_state else None
        sync_delay_seconds = self._sync_delay_seconds(last_sync_at)

        if not self.settings.feishu_chat_enabled:
            availability = "maintenance"
            blocked_reason = "chat_disabled"
        elif sync_status == "blocked":
            availability = "sync_blocked"
            blocked_reason = "sync_blocked"
        elif membership_status == "unknown":
            availability = "membership_unknown"
            blocked_reason = "membership_not_synchronized"
        elif membership_status == "stale":
            availability = "membership_stale"
            blocked_reason = "membership_snapshot_stale"
        elif membership_status == "not_member":
            availability = "not_chat_member"
            blocked_reason = "not_chat_member"
        elif credential_status in {"authorization_required", "revoked"}:
            availability = "authorization_required"
            blocked_reason = "authorization_required"
        elif sync_status in {"disabled", "backfilling"}:
            availability = "backfilling"
            blocked_reason = "initial_sync_pending"
        elif sync_status in {"delayed", "rate_limited"}:
            availability = "sync_delayed"
            blocked_reason = "sync_delayed"
        else:
            availability = "ready"
            blocked_reason = None

        can_read = availability in {"ready", "sync_delayed"}
        can_send = can_read and credential_status == "active"
        return AgentRuntimeStatus(
            availability=availability,
            credential_status=credential_status,
            membership_status=membership_status,
            sync_status=sync_status,
            can_read=can_read,
            can_send=can_send,
            blocked_reason=blocked_reason,
            last_sync_at=last_sync_at,
            sync_delay_seconds=sync_delay_seconds,
        )

    def replace_agent_access(
        self,
        agent_id: int,
        *,
        user_ids: list[int],
        group_ids: list[int],
        actor: User,
    ) -> dict:
        agent = self.get_agent_by_id(agent_id)
        wanted_user_ids = set(user_ids)
        wanted_group_ids = set(group_ids)
        self._validate_users(wanted_user_ids)
        self._validate_groups(wanted_group_ids)
        now = utcnow()
        self._replace_grants(
            AiAgentUserGrant,
            owner_field="user_id",
            agent_id=agent.id,
            wanted_ids=wanted_user_ids,
            actor_id=actor.id,
            now=now,
        )
        self._replace_grants(
            AiAgentGroupGrant,
            owner_field="group_id",
            agent_id=agent.id,
            wanted_ids=wanted_group_ids,
            actor_id=actor.id,
            now=now,
        )
        self._request_member_resync(agent.id, now)
        agent.updated_by = actor.id
        self.db.commit()
        return self.serialize_agent_access(agent)

    def update_agent_presentation(
        self,
        agent_id: int,
        *,
        name: str,
        description: str,
        actor: User,
    ) -> dict:
        agent = self.get_agent_by_id(agent_id)
        agent.name = name
        agent.description = description
        agent.updated_by = actor.id
        self.db.commit()
        self.db.refresh(agent)
        return self.serialize_admin_agent(agent)

    def get_agent_feishu_chat_config(self, agent_id: int) -> dict:
        agent = self.get_agent_by_id(agent_id)
        return self._serialize_feishu_chat_config(
            resolve_agent_chat_config(agent, self.settings)
        )

    def update_agent_feishu_chat_config(
        self,
        agent_id: int,
        *,
        config: AgentChatConfig,
        actor: User,
    ) -> dict:
        agent = self.get_agent_by_id(agent_id)
        store_agent_chat_config(agent, config)
        agent.updated_by = actor.id
        now = utcnow()
        sync_state = self.db.scalar(
            select(FeishuChatSyncState).where(
                FeishuChatSyncState.agent_id == agent.id,
                FeishuChatSyncState.chat_id == config.target_chat_id,
                FeishuChatSyncState.deleted_at.is_(None),
            )
        )
        if sync_state is not None:
            sync_state.last_member_sync_at = None
            sync_state.next_sync_at = now
        self.db.commit()
        self.db.refresh(agent)
        return self._serialize_feishu_chat_config(config)

    async def upload_agent_avatar(
        self,
        agent_id: int,
        *,
        file: UploadFile,
        actor: User,
    ) -> dict:
        agent = self.get_agent_by_id(agent_id)
        content = await file.read(MAX_AGENT_AVATAR_BYTES + 1)
        if len(content) > MAX_AGENT_AVATAR_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent avatar file is too large",
            )
        try:
            suffix = validate_raster_image(
                content,
                filename=file.filename,
                content_type=file.content_type,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(exc),
            ) from exc

        AGENT_AVATAR_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        filename = (
            f"agent-{agent.id}-{utcnow().strftime('%Y%m%d%H%M%S')}-"
            f"{secrets.token_hex(4)}{suffix}"
        )
        path = AGENT_AVATAR_UPLOAD_DIR / filename
        path.write_bytes(content)

        previous_url = agent.avatar_url
        agent.avatar_url = f"{AGENT_AVATAR_URL_PREFIX}{filename}"
        agent.updated_by = actor.id
        try:
            self.db.commit()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        self.db.refresh(agent)
        delete_managed_upload(
            previous_url,
            AGENT_AVATAR_URL_PREFIX,
            AGENT_AVATAR_UPLOAD_DIR,
        )
        return self.serialize_admin_agent(agent)

    def remove_agent_avatar(self, agent_id: int, *, actor: User) -> dict:
        agent = self.get_agent_by_id(agent_id)
        previous_url = agent.avatar_url
        agent.avatar_url = None
        agent.updated_by = actor.id
        self.db.commit()
        self.db.refresh(agent)
        delete_managed_upload(
            previous_url,
            AGENT_AVATAR_URL_PREFIX,
            AGENT_AVATAR_UPLOAD_DIR,
        )
        return self.serialize_admin_agent(agent)

    @staticmethod
    def _serialize_feishu_chat_config(config: AgentChatConfig) -> dict:
        return {
            **config.serialize(),
            "complete": config.complete,
        }

    def get_agent_by_id(self, agent_id: int) -> AiAgent:
        agent = self.db.scalar(
            select(AiAgent).where(AiAgent.id == agent_id, AiAgent.deleted_at.is_(None))
        )
        if agent is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent not found")
        return agent

    def list_admin_agents(self) -> list[dict]:
        agents = self.db.scalars(
            select(AiAgent)
            .where(AiAgent.deleted_at.is_(None))
            .order_by(AiAgent.sort_order, AiAgent.id)
        ).all()
        return [self.serialize_admin_agent(agent) for agent in agents]

    def serialize_admin_agent(self, agent: AiAgent) -> dict:
        counts = self._access_counts(agent)
        return {
            "id": agent.id,
            "agent_key": agent.agent_key,
            "name": agent.name,
            "description": agent.description,
            "avatar_url": agent.avatar_url,
            "implementation_type": agent.implementation_type,
            "enabled": agent.enabled,
            "sort_order": agent.sort_order,
            **counts,
        }

    def serialize_agent_access(self, agent: AiAgent) -> dict:
        direct_users = self.db.scalars(
            select(User)
            .join(AiAgentUserGrant, AiAgentUserGrant.user_id == User.id)
            .where(
                AiAgentUserGrant.agent_id == agent.id,
                AiAgentUserGrant.deleted_at.is_(None),
                User.deleted_at.is_(None),
            )
            .order_by(User.name, User.id)
        ).all()
        groups = self.db.scalars(
            select(Group)
            .join(AiAgentGroupGrant, AiAgentGroupGrant.group_id == Group.id)
            .where(
                AiAgentGroupGrant.agent_id == agent.id,
                AiAgentGroupGrant.deleted_at.is_(None),
                Group.deleted_at.is_(None),
            )
            .order_by(Group.name, Group.id)
        ).all()
        return {
            "agent": self.serialize_admin_agent(agent),
            "users": [
                {
                    "id": user.id,
                    "name": user.name,
                    "avatar_url": user.avatar_url,
                    "status": user.status,
                }
                for user in direct_users
            ],
            "groups": [
                {
                    "id": group.id,
                    "name": group.name,
                    "member_count": self._group_member_count(group.id),
                }
                for group in groups
            ],
        }

    def _credential_status(self, user_id: int) -> str:
        credential = self.db.scalar(
            select(FeishuUserCredential).where(
                FeishuUserCredential.user_id == user_id,
                FeishuUserCredential.deleted_at.is_(None),
            )
        )
        if credential is None or credential.status == "reauthorization_required":
            return "authorization_required"
        if credential.status == "refreshing":
            return "refreshing"
        if credential.status == "revoked":
            return "revoked"
        if credential.status != "active":
            return "authorization_required"
        if (
            not credential.access_token_encrypted
            or credential.access_token_expires_at is None
            or not credential.refresh_token_encrypted
            or credential.refresh_token_expires_at is None
            or credential.refresh_token_expires_at <= utcnow()
            or missing_required_chat_scopes(
                frozenset(credential.granted_scopes_json or [])
            )
        ):
            return "authorization_required"
        return "active"

    def _sync_state(self, agent: AiAgent) -> FeishuChatSyncState | None:
        chat_id = resolve_agent_chat_config(agent, self.settings).target_chat_id
        if not chat_id:
            return None
        return self.db.scalar(
            select(FeishuChatSyncState).where(
                FeishuChatSyncState.agent_id == agent.id,
                FeishuChatSyncState.chat_id == chat_id,
                FeishuChatSyncState.deleted_at.is_(None),
            )
        )

    def _membership_status(
        self,
        user: User,
        sync_state: FeishuChatSyncState | None,
    ) -> str:
        if sync_state is None or sync_state.last_member_sync_at is None:
            return "unknown"
        snapshot_age = utcnow() - sync_state.last_member_sync_at
        max_age = timedelta(
            seconds=self.settings.feishu_chat_member_snapshot_max_age_seconds
        )
        if snapshot_age < timedelta(0) or snapshot_age > max_age:
            return "stale"
        membership = self.db.scalar(
            select(FeishuChatMember.id).where(
                FeishuChatMember.chat_id == sync_state.chat_id,
                FeishuChatMember.member_id == user.feishu_open_id,
                FeishuChatMember.member_id_type == "open_id",
                FeishuChatMember.is_active.is_(True),
                FeishuChatMember.deleted_at.is_(None),
            )
        )
        return "active" if membership is not None else "not_member"

    def _sync_status(self, sync_state: FeishuChatSyncState | None) -> str:
        if sync_state is None:
            return "disabled"
        allowed = {
            "disabled",
            "backfilling",
            "healthy",
            "delayed",
            "rate_limited",
            "blocked",
        }
        return sync_state.status if sync_state.status in allowed else "blocked"

    def _sync_delay_seconds(self, last_sync_at) -> int | None:
        if last_sync_at is None:
            return None
        return max(0, int((utcnow() - last_sync_at).total_seconds()))

    def _access_counts(self, agent: AiAgent) -> dict[str, int]:
        direct_ids = set(
            self.db.scalars(
                select(AiAgentUserGrant.user_id)
                .join(User, User.id == AiAgentUserGrant.user_id)
                .where(
                    AiAgentUserGrant.agent_id == agent.id,
                    AiAgentUserGrant.deleted_at.is_(None),
                    User.deleted_at.is_(None),
                    User.status == "active",
                )
            ).all()
        )
        group_ids = set(
            self.db.scalars(
                select(AiAgentGroupGrant.group_id)
                .join(Group, Group.id == AiAgentGroupGrant.group_id)
                .where(
                    AiAgentGroupGrant.agent_id == agent.id,
                    AiAgentGroupGrant.deleted_at.is_(None),
                    Group.deleted_at.is_(None),
                )
            ).all()
        )
        group_user_ids: set[int] = set()
        if group_ids:
            group_user_ids = set(
                self.db.scalars(
                    select(GroupMember.user_id)
                    .join(User, User.id == GroupMember.user_id)
                    .where(
                        GroupMember.group_id.in_(group_ids),
                        GroupMember.deleted_at.is_(None),
                        User.deleted_at.is_(None),
                        User.status == "active",
                    )
                ).all()
            )
        effective_ids = direct_ids | group_user_ids
        chat_id = resolve_agent_chat_config(agent, self.settings).target_chat_id
        member_user_ids = self._active_chat_member_user_ids(effective_ids, chat_id)
        return {
            "direct_user_count": len(direct_ids),
            "group_count": len(group_ids),
            "effective_user_count": len(effective_ids),
            "chat_member_count": len(member_user_ids),
            "non_chat_member_count": len(effective_ids - member_user_ids),
        }

    def _active_chat_member_user_ids(
        self,
        user_ids: set[int],
        chat_id: str,
    ) -> set[int]:
        if not chat_id or not user_ids:
            return set()
        return set(
            self.db.scalars(
                select(User.id)
                .join(
                    FeishuChatMember,
                    FeishuChatMember.member_id == User.feishu_open_id,
                )
                .where(
                    User.id.in_(user_ids),
                    FeishuChatMember.chat_id == chat_id,
                    FeishuChatMember.member_id_type == "open_id",
                    FeishuChatMember.is_active.is_(True),
                    FeishuChatMember.deleted_at.is_(None),
                )
            ).all()
        )

    def _group_member_count(self, group_id: int) -> int:
        return len(
            self.db.scalars(
                select(GroupMember.id).where(
                    GroupMember.group_id == group_id,
                    GroupMember.deleted_at.is_(None),
                )
            ).all()
        )

    def _validate_users(self, user_ids: set[int]) -> None:
        if not user_ids:
            return
        valid_ids = set(
            self.db.scalars(
                select(User.id).where(User.id.in_(user_ids), User.deleted_at.is_(None))
            ).all()
        )
        unknown = sorted(user_ids - valid_ids)
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "unknown_users", "ids": unknown},
            )

    def _validate_groups(self, group_ids: set[int]) -> None:
        if not group_ids:
            return
        valid_ids = set(
            self.db.scalars(
                select(Group.id).where(Group.id.in_(group_ids), Group.deleted_at.is_(None))
            ).all()
        )
        unknown = sorted(group_ids - valid_ids)
        if unknown:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "unknown_groups", "ids": unknown},
            )

    def _replace_grants(
        self,
        model,
        *,
        owner_field: str,
        agent_id: int,
        wanted_ids: set[int],
        actor_id: int,
        now,
    ) -> None:
        rows = list(
            self.db.scalars(
                select(model)
                .where(model.agent_id == agent_id)
                .order_by(model.id.desc())
            ).all()
        )
        rows_by_owner: dict[int, list] = {}
        for row in rows:
            rows_by_owner.setdefault(getattr(row, owner_field), []).append(row)

        for owner_id, owner_rows in rows_by_owner.items():
            active_rows = [row for row in owner_rows if row.deleted_at is None]
            if owner_id not in wanted_ids:
                for row in active_rows:
                    row.deleted_at = now
                    row.updated_by = actor_id
                continue
            if active_rows:
                for row in active_rows:
                    row.updated_by = actor_id
                continue
            restored = owner_rows[0]
            restored.deleted_at = None
            restored.updated_by = actor_id

        for owner_id in wanted_ids - set(rows_by_owner):
            self.db.add(
                model(
                    agent_id=agent_id,
                    **{owner_field: owner_id},
                    created_by=actor_id,
                    updated_by=actor_id,
                )
            )

    def _request_member_resync(self, agent_id: int, now: datetime) -> None:
        agent = self.get_agent_by_id(agent_id)
        chat_id = resolve_agent_chat_config(agent, self.settings).target_chat_id
        if not chat_id:
            return
        sync_state = self.db.scalar(
            select(FeishuChatSyncState).where(
                FeishuChatSyncState.agent_id == agent_id,
                FeishuChatSyncState.chat_id == chat_id,
                FeishuChatSyncState.deleted_at.is_(None),
            )
        )
        if sync_state is None:
            return
        sync_state.next_sync_at = now
