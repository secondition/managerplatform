from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


ChatAgentAvailability = Literal[
    "authorization_required",
    "not_chat_member",
    "membership_unknown",
    "membership_stale",
    "backfilling",
    "sync_delayed",
    "sync_blocked",
    "ready",
    "maintenance",
]

ChatCredentialStatus = Literal[
    "active",
    "authorization_required",
    "refreshing",
    "revoked",
]

ChatMembershipStatus = Literal["active", "not_member", "unknown", "stale"]

ChatSyncStatus = Literal[
    "disabled",
    "backfilling",
    "healthy",
    "delayed",
    "rate_limited",
    "blocked",
]


class ChatAgentSummaryOut(BaseModel):
    agent_key: str
    name: str
    description: str
    avatar_url: str | None
    implementation_type: Literal["feishu_group_projection"]
    platform_granted: bool
    status: ChatAgentAvailability


class ChatAgentStatusOut(BaseModel):
    agent_key: str
    platform_granted: bool
    credential_status: ChatCredentialStatus
    membership_status: ChatMembershipStatus
    sync_status: ChatSyncStatus
    can_read: bool
    can_send: bool
    blocked_reason: str | None
    last_sync_at: datetime | None
    sync_delay_seconds: int | None


class ChatAuthorizeOut(BaseModel):
    authorize_url: str = Field(max_length=4096)
    return_to: str = Field(max_length=500)


class ChatOAuthCallbackIn(BaseModel):
    code: str = Field(min_length=1, max_length=2048)
    state: str = Field(min_length=1, max_length=4096)


class ChatOAuthCallbackOut(BaseModel):
    agent_key: str
    credential_status: Literal["active"]
    return_to: str


class ChatDisconnectOut(BaseModel):
    ok: bool
    credential_status: Literal["revoked"]


class UserTextMessageOut(BaseModel):
    id: str
    role: Literal["user"]
    kind: Literal["user_text"]
    body_text: str
    created_at: datetime


class AssistantMarkdownMessageOut(BaseModel):
    id: str
    role: Literal["assistant"]
    kind: Literal["assistant_markdown"]
    body_markdown: str
    created_at: datetime


class AssistantFileMessageOut(BaseModel):
    id: str
    role: Literal["assistant"]
    kind: Literal["assistant_file"]
    file_name: str
    file_type: str | None
    file_size: int | None
    download_status: Literal[
        "available",
        "preparing",
        "too_large",
        "unavailable",
        "view_in_feishu",
    ]
    download_url: str | None
    created_at: datetime


class UnsupportedChatMessageOut(BaseModel):
    id: str
    role: Literal["assistant"]
    kind: Literal["unsupported"]
    label: str
    created_at: datetime


ChatMessageOut = Annotated[
    UserTextMessageOut
    | AssistantMarkdownMessageOut
    | AssistantFileMessageOut
    | UnsupportedChatMessageOut,
    Field(discriminator="kind"),
]


class ChatMessagePageOut(BaseModel):
    items: list[ChatMessageOut]
    next_cursor: str | None
    has_more: bool


ClientRequestId = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        min_length=8,
        max_length=80,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
]


class SendChatMessageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=50_000)
    client_request_id: ClientRequestId


class SendChatMessageOut(BaseModel):
    client_request_id: str
    status: Literal["sending", "sent_to_feishu", "synced", "failed"]
    message_id: str | None
    error_code: str | None
    error_message: str | None
