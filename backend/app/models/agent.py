from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.db.types import BigInt, JSONText


class AiAgent(Base, TimestampMixin, AuditMixin):
    __tablename__ = "ai_agents"
    __table_args__ = (
        Index(
            "uq_ai_agents_agent_key_active",
            "agent_key",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    agent_key: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    implementation_type: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    config_json: Mapped[dict | None] = mapped_column(JSONText, nullable=True)

    user_grants: Mapped[list["AiAgentUserGrant"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )
    group_grants: Mapped[list["AiAgentGroupGrant"]] = relationship(
        back_populates="agent",
        cascade="all, delete-orphan",
    )


class AiAgentUserGrant(Base, TimestampMixin, AuditMixin):
    __tablename__ = "ai_agent_user_grants"
    __table_args__ = (
        Index("ix_ai_agent_user_grants_user", "user_id", "agent_id"),
        Index(
            "uq_ai_agent_user_grants_active",
            "agent_id",
            "user_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("ai_agents.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    agent: Mapped[AiAgent] = relationship(back_populates="user_grants")
    user = relationship("User")


class AiAgentGroupGrant(Base, TimestampMixin, AuditMixin):
    __tablename__ = "ai_agent_group_grants"
    __table_args__ = (
        Index("ix_ai_agent_group_grants_group", "group_id", "agent_id"),
        Index(
            "uq_ai_agent_group_grants_active",
            "agent_id",
            "group_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    agent_id: Mapped[int] = mapped_column(ForeignKey("ai_agents.id"), nullable=False)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)

    agent: Mapped[AiAgent] = relationship(back_populates="group_grants")
    group = relationship("Group")
