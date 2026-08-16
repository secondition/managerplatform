from __future__ import annotations

from dataclasses import asdict, dataclass

from app.core.config import Settings
from app.models.agent import AiAgent


AGENT_CHAT_CONFIG_KEY = "feishu_chat"


@dataclass(frozen=True)
class AgentChatConfig:
    target_chat_id: str = ""
    target_chat_name: str = ""
    agent_sender_id: str = ""
    agent_mention_id: str = ""
    agent_display_name: str = ""

    @property
    def complete(self) -> bool:
        return all(value.strip() for value in asdict(self).values())

    def serialize(self) -> dict[str, str]:
        return asdict(self)


def resolve_agent_chat_config(
    agent: AiAgent,
    runtime_settings: Settings,
) -> AgentChatConfig:
    config_json = agent.config_json if isinstance(agent.config_json, dict) else {}
    stored = config_json.get(AGENT_CHAT_CONFIG_KEY)
    if isinstance(stored, dict):
        return AgentChatConfig(
            target_chat_id=_string(stored.get("target_chat_id")),
            target_chat_name=_string(stored.get("target_chat_name")),
            agent_sender_id=_string(stored.get("agent_sender_id")),
            agent_mention_id=_string(stored.get("agent_mention_id")),
            agent_display_name=_string(stored.get("agent_display_name")),
        )
    return legacy_agent_chat_config(runtime_settings)


def legacy_agent_chat_config(runtime_settings: Settings) -> AgentChatConfig:
    return AgentChatConfig(
        target_chat_id=runtime_settings.feishu_chat_target_chat_id.strip(),
        target_chat_name=runtime_settings.feishu_chat_target_chat_name.strip(),
        agent_sender_id=runtime_settings.feishu_chat_agent_sender_id.strip(),
        agent_mention_id=runtime_settings.feishu_chat_agent_mention_id.strip(),
        agent_display_name=runtime_settings.feishu_chat_agent_display_name.strip(),
    )


def store_agent_chat_config(agent: AiAgent, config: AgentChatConfig) -> None:
    config_json = dict(agent.config_json) if isinstance(agent.config_json, dict) else {}
    config_json[AGENT_CHAT_CONFIG_KEY] = config.serialize()
    agent.config_json = config_json


def _string(value) -> str:
    return value.strip() if isinstance(value, str) else ""
