from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.db.types import BigInt


class Department(Base, TimestampMixin, AuditMixin):
    __tablename__ = "departments"
    __table_args__ = (Index("ix_departments_feishu_department_id", "feishu_department_id", unique=True),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("departments.id"), nullable=True)
    feishu_department_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    parent: Mapped["Department | None"] = relationship(remote_side=[id])


class Group(Base, TimestampMixin, AuditMixin):
    """人员组：手动管理的成员集合。source 标记来源（department=从部门导入创建，
    manual=手工创建），但生成后与部门解耦，成员完全自由编辑。派发给组时在前端
    展开为组内每个成员，故任务/指标表不引用 group。"""

    __tablename__ = "groups"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(20), default="manual", nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    members: Mapped[list["GroupMember"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
    )


class GroupMember(Base, TimestampMixin, AuditMixin):
    __tablename__ = "group_members"
    __table_args__ = (Index("uq_group_members_group_user", "group_id", "user_id", unique=True),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    group_id: Mapped[int] = mapped_column(ForeignKey("groups.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    group: Mapped[Group] = relationship(back_populates="members")
    user = relationship("User")


class ContactSyncLog(Base, TimestampMixin, AuditMixin):
    __tablename__ = "contact_sync_logs"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="running", nullable=False)
    created_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    disabled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    skipped_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class CompanySetting(Base, TimestampMixin, AuditMixin):
    __tablename__ = "company_settings"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    company_name: Mapped[str] = mapped_column(String(100), default="企业工作管理平台", nullable=False)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    footer_text: Mapped[str] = mapped_column(
        String(200),
        default="WORK MANAGEMENT DESK · 企业工作管理平台 MVP",
        nullable=False,
    )
