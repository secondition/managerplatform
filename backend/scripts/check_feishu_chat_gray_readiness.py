from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import func, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings, validate_feishu_chat_settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.agent import AiAgent, AiAgentGroupGrant, AiAgentUserGrant  # noqa: E402
from app.models.feishu_chat import (  # noqa: E402
    FeishuChatMember,
    FeishuChatMessage,
    FeishuChatSyncState,
    FeishuUserCredential,
)
from app.models.user import User  # noqa: E402

MIN_GRAY_USERS = 3
MAX_GRAY_USERS = 5


def main() -> int:
    blockers: list[str] = []
    warnings: list[str] = []

    print("Feishu chat gray readiness")
    print(f"app_environment={settings.app_environment}")
    print(f"chat_environment={settings.feishu_chat_environment}")
    print(f"chat_enabled={str(settings.feishu_chat_enabled).lower()}")
    print(f"phase0_disabled={str(not settings.feishu_chat_phase0_enabled).lower()}")
    print(
        "target_is_named_test_group="
        f"{str(settings.feishu_chat_target_chat_name.strip() == '测试群').lower()}"
    )

    if settings.app_environment == "production":
        blockers.append("gray_test_must_not_run_in_production_app_environment")
    if settings.feishu_chat_environment != "test":
        blockers.append("gray_test_requires_test_chat_environment")
    if settings.feishu_chat_phase0_enabled:
        blockers.append("phase0_tool_must_be_disabled")
    if settings.feishu_chat_target_chat_name.strip() != "测试群":
        blockers.append("target_group_name_is_not_test_group")

    try:
        validate_feishu_chat_settings(
            settings.model_copy(update={"feishu_chat_enabled": True})
        )
        print("enabled_config_validation=ready")
    except RuntimeError as exc:
        print("enabled_config_validation=blocked")
        blockers.append(_safe_config_reason(str(exc)))

    db = SessionLocal()
    try:
        agent = db.scalar(
            select(AiAgent).where(
                AiAgent.agent_key == "chabao",
                AiAgent.deleted_at.is_(None),
            )
        )
        print(f"agent_present={str(agent is not None).lower()}")
        print(f"agent_enabled={str(bool(agent and agent.enabled)).lower()}")
        if agent is None:
            blockers.append("chabao_agent_missing")
            direct_grants = 0
            group_grants = 0
        else:
            direct_grants = _count(
                db,
                select(func.count())
                .select_from(AiAgentUserGrant)
                .join(User, User.id == AiAgentUserGrant.user_id)
                .where(
                    AiAgentUserGrant.agent_id == agent.id,
                    AiAgentUserGrant.deleted_at.is_(None),
                    User.deleted_at.is_(None),
                    User.status == "active",
                ),
            )
            group_grants = _count(
                db,
                select(func.count())
                .select_from(AiAgentGroupGrant)
                .where(
                    AiAgentGroupGrant.agent_id == agent.id,
                    AiAgentGroupGrant.deleted_at.is_(None),
                ),
            )
            if not agent.enabled:
                blockers.append("chabao_agent_disabled")

        active_users = _count(
            db,
            select(func.count()).select_from(User).where(
                User.status == "active",
                User.deleted_at.is_(None),
            ),
        )
        credential_rows = _count(
            db,
            select(func.count()).select_from(FeishuUserCredential).where(
                FeishuUserCredential.deleted_at.is_(None),
            ),
        )
        sync_state_rows = _count(
            db,
            select(func.count()).select_from(FeishuChatSyncState).where(
                FeishuChatSyncState.deleted_at.is_(None),
            ),
        )
        cached_messages = _count(
            db,
            select(func.count()).select_from(FeishuChatMessage),
        )
        active_members = _count(
            db,
            select(func.count()).select_from(FeishuChatMember).where(
                FeishuChatMember.is_active.is_(True),
                FeishuChatMember.deleted_at.is_(None),
            ),
        )

        print(f"active_platform_users={active_users}")
        print(f"direct_gray_grants={direct_grants}")
        print(f"group_grants={group_grants}")
        print(f"credential_rows={credential_rows}")
        print(f"sync_state_rows={sync_state_rows}")
        print(f"cached_messages={cached_messages}")
        print(f"active_member_rows={active_members}")

        if active_users < MIN_GRAY_USERS:
            blockers.append("fewer_than_three_active_platform_users")
        if not MIN_GRAY_USERS <= direct_grants <= MAX_GRAY_USERS:
            blockers.append("direct_gray_grants_must_be_between_three_and_five")
        if group_grants:
            blockers.append("group_grants_must_be_empty_during_initial_gray_test")
        if credential_rows < direct_grants:
            warnings.append("some_gray_users_have_not_completed_chat_oauth")
        if sync_state_rows == 0:
            warnings.append("initial_chat_sync_has_not_started")
    finally:
        db.close()

    for warning in warnings:
        print(f"warning={warning}")
    for blocker in dict.fromkeys(blockers):
        print(f"blocker={blocker}")
    ready = not blockers
    print(f"gray_readiness={'ready' if ready else 'blocked'}")
    return 0 if ready else 1


def _count(db, statement) -> int:
    return int(db.scalar(statement) or 0)


def _safe_config_reason(message: str) -> str:
    allowed = {
        "FEISHU_CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key when chat is enabled": (
            "credential_encryption_key_missing_or_invalid"
        ),
        "JWT_SECRET must be a non-default value of at least 32 characters when chat is enabled": (
            "jwt_secret_not_ready"
        ),
    }
    if message in allowed:
        return allowed[message]
    if message.startswith("Missing Feishu chat settings:"):
        return "required_chat_configuration_missing"
    return "enabled_chat_configuration_invalid"


if __name__ == "__main__":
    raise SystemExit(main())
