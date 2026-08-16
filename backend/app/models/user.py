from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.db.types import BigInt


class User(Base, TimestampMixin, AuditMixin):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_feishu_union_id_active",
            "feishu_union_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index(
            "uq_users_feishu_open_id_active",
            "feishu_open_id",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    profile_signature: Mapped[str | None] = mapped_column(String(200), nullable=True)
    role: Mapped[str] = mapped_column(String(30), default="member", nullable=False)
    feishu_union_id: Mapped[str] = mapped_column(String(80), nullable=False)
    feishu_open_id: Mapped[str] = mapped_column(String(80), nullable=False)
    feishu_user_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    feishu_message_receive_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    feishu_message_receive_id_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    sync_source: Mapped[str] = mapped_column(String(30), default="feishu", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    disabled_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    token_version: Mapped[int] = mapped_column(default=0, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    department = relationship("Department")
    permissions: Mapped[list["UserPermission"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


class UserPermission(Base, TimestampMixin, AuditMixin):
    __tablename__ = "user_permissions"
    __table_args__ = (
        Index("ix_user_permissions_user_permission", "user_id", "permission"),
        Index(
            "uq_user_permissions_user_permission_active",
            "user_id",
            "permission",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    permission: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped[User] = relationship(back_populates="permissions")


class RefreshToken(Base, TimestampMixin, AuditMixin):
    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_token_hash", "token_hash", unique=True),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(300), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship()
