from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.db.types import BigInt, JSONText


class FeishuUserCredential(Base, TimestampMixin, AuditMixin):
    __tablename__ = "feishu_user_credentials"
    __table_args__ = (
        Index(
            "uq_feishu_user_credentials_user_active",
            "user_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_feishu_user_credentials_status", "status", "access_token_expires_at"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    access_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    granted_scopes_json: Mapped[list | None] = mapped_column(JSONText, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    refresh_lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_refreshed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User")


class FeishuChatSyncState(Base, TimestampMixin, AuditMixin):
    __tablename__ = "feishu_chat_sync_states"
    __table_args__ = (
        Index(
            "uq_feishu_chat_sync_states_agent_chat_active",
            "agent_id",
            "chat_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_feishu_chat_sync_states_due", "status", "next_sync_at"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("ai_agents.id"), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="disabled", nullable=False)
    sync_mode: Mapped[str] = mapped_column(String(30), default="backfill", nullable=False)
    backfill_start_time_ms: Mapped[int | None] = mapped_column(BigInt, nullable=True)
    current_window_start_time_ms: Mapped[int | None] = mapped_column(BigInt, nullable=True)
    current_window_end_time_ms: Mapped[int | None] = mapped_column(BigInt, nullable=True)
    last_page_token: Mapped[str | None] = mapped_column(String(500), nullable=True)
    last_message_create_time_ms: Mapped[int | None] = mapped_column(BigInt, nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_message_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_member_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rate_limited_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    agent = relationship("AiAgent")


class FeishuChatMessage(Base, TimestampMixin):
    __tablename__ = "feishu_chat_messages"
    __table_args__ = (
        Index("uq_feishu_chat_messages_message_id", "message_id", unique=True),
        Index("ix_feishu_chat_messages_chat_created", "chat_id", "create_time_ms"),
        Index(
            "ix_feishu_chat_messages_chat_sender_created",
            "chat_id",
            "sender_id",
            "create_time_ms",
        ),
        Index("ix_feishu_chat_messages_parent", "parent_id"),
        Index("ix_feishu_chat_messages_root", "root_id"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    message_id: Mapped[str] = mapped_column(String(120), nullable=False)
    chat_id: Mapped[str] = mapped_column(String(120), nullable=False)
    sender_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sender_id_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    sender_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    msg_type: Mapped[str] = mapped_column(String(40), nullable=False)
    content_json: Mapped[dict | list | None] = mapped_column(JSONText, nullable=True)
    mentions_json: Mapped[list | None] = mapped_column(JSONText, nullable=True)
    parent_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    root_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    create_time_ms: Mapped[int] = mapped_column(BigInt, nullable=False)
    update_time_ms: Mapped[int | None] = mapped_column(BigInt, nullable=True)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    updated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class FeishuChatMember(Base, TimestampMixin):
    __tablename__ = "feishu_chat_members"
    __table_args__ = (
        Index(
            "uq_feishu_chat_members_identity_active",
            "chat_id",
            "member_id",
            "member_id_type",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_feishu_chat_members_lookup", "chat_id", "member_id", "is_active"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    chat_id: Mapped[str] = mapped_column(String(120), nullable=False)
    member_id: Mapped[str] = mapped_column(String(120), nullable=False)
    member_id_type: Mapped[str] = mapped_column(String(30), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    member_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    synced_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class ChatSendRequest(Base, TimestampMixin, AuditMixin):
    __tablename__ = "chat_send_requests"
    __table_args__ = (
        Index(
            "uq_chat_send_requests_client_active",
            "user_id",
            "agent_id",
            "client_request_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_chat_send_requests_status", "status", "updated_at"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    agent_id: Mapped[int] = mapped_column(ForeignKey("ai_agents.id"), nullable=False)
    client_request_id: Mapped[str] = mapped_column(String(80), nullable=False)
    feishu_uuid: Mapped[str] = mapped_column(String(80), nullable=False)
    request_text_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="sending", nullable=False)
    feishu_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User")
    agent = relationship("AiAgent")
