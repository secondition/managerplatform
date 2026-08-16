from __future__ import annotations

import sys
from pathlib import Path

from sqlalchemy import select


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.db.session import SessionLocal  # noqa: E402
from app.models.agent import AiAgent  # noqa: E402
from app.services.agent_chat_config import (  # noqa: E402
    AGENT_CHAT_CONFIG_KEY,
    AgentChatConfig,
    legacy_agent_chat_config,
    store_agent_chat_config,
)


LEGACY_ENV_KEYS = {
    "FEISHU_CHAT_TARGET_CHAT_ID": "target_chat_id",
    "FEISHU_CHAT_TARGET_CHAT_NAME": "target_chat_name",
    "FEISHU_CHAT_AGENT_SENDER_ID": "agent_sender_id",
    "FEISHU_CHAT_AGENT_MENTION_ID": "agent_mention_id",
    "FEISHU_CHAT_AGENT_DISPLAY_NAME": "agent_display_name",
}


def main() -> int:
    legacy_config = legacy_agent_chat_config(settings)
    if not legacy_config.complete:
        legacy_config = _read_last_non_empty_legacy_config()
        if not legacy_config.complete:
            print("legacy_feishu_chat_config=missing")
            return 2

    db = SessionLocal()
    try:
        agent = db.scalar(
            select(AiAgent).where(
                AiAgent.agent_key == "chabao",
                AiAgent.deleted_at.is_(None),
            )
        )
        if agent is None:
            print("chabao_agent=missing")
            return 3
        config_json = agent.config_json if isinstance(agent.config_json, dict) else {}
        if isinstance(config_json.get(AGENT_CHAT_CONFIG_KEY), dict):
            print("agent_feishu_chat_config=already_present")
            return 0
        store_agent_chat_config(agent, legacy_config)
        db.commit()
        print("agent_feishu_chat_config=migrated")
        return 0
    finally:
        db.close()


def _read_last_non_empty_legacy_config() -> AgentChatConfig:
    values: dict[str, str] = {}
    env_path = BACKEND_DIR / ".env"
    if env_path.is_file():
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, raw_value = line.split("=", 1)
            field = LEGACY_ENV_KEYS.get(key.strip())
            value = raw_value.strip().strip('"').strip("'")
            if field and value:
                values[field] = value
    return AgentChatConfig(**values)


if __name__ == "__main__":
    raise SystemExit(main())
