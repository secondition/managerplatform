from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AdminAgentOut(BaseModel):
    id: int
    agent_key: str
    name: str
    description: str
    avatar_url: str | None
    implementation_type: str
    enabled: bool
    sort_order: int
    direct_user_count: int
    group_count: int
    effective_user_count: int
    chat_member_count: int
    non_chat_member_count: int


class AgentAccessUserOut(BaseModel):
    id: int
    name: str
    avatar_url: str | None
    status: str


class AgentAccessGroupOut(BaseModel):
    id: int
    name: str
    member_count: int


class AgentAccessOut(BaseModel):
    agent: AdminAgentOut
    users: list[AgentAccessUserOut]
    groups: list[AgentAccessGroupOut]


class AgentPresentationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    description: str = Field(max_length=1000)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name must not be blank")
        return normalized

    @field_validator("description")
    @classmethod
    def normalize_description(cls, value: str) -> str:
        return value.strip()


class AgentFeishuChatConfigOut(BaseModel):
    target_chat_id: str
    target_chat_name: str
    agent_sender_id: str
    agent_mention_id: str
    agent_display_name: str
    complete: bool


class AgentFeishuChatConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_chat_id: str = Field(min_length=1, max_length=200)
    target_chat_name: str = Field(min_length=1, max_length=200)
    agent_sender_id: str = Field(min_length=1, max_length=200)
    agent_mention_id: str = Field(min_length=1, max_length=200)
    agent_display_name: str = Field(min_length=1, max_length=100)

    @field_validator(
        "target_chat_id",
        "target_chat_name",
        "agent_sender_id",
        "agent_mention_id",
        "agent_display_name",
    )
    @classmethod
    def normalize_required_string(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value must not be blank")
        return normalized


class AgentAccessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_ids: list[int] = Field(default_factory=list)
    group_ids: list[int] = Field(default_factory=list)

    @field_validator("user_ids", "group_ids")
    @classmethod
    def normalize_ids(cls, values: list[int]) -> list[int]:
        if any(value <= 0 for value in values):
            raise ValueError("ids must be positive")
        return sorted(set(values))
