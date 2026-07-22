from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.db.types import BigInt

if TYPE_CHECKING:
    from app.models.user import User


class OkrObjective(Base, TimestampMixin, AuditMixin):
    """A monthly OKR objective owned by a single user.

    Objectives are scoped per month (``YYYY-MM``); switching months starts a
    blank slate — there is no carry-over. ``progress`` is the stored average of
    active key-result progress markers.
    AI quality reviews are stored for the whole OKR set in ``okr_reviews``.
    """

    __tablename__ = "okr_objectives"
    __table_args__ = (Index("ix_okr_objectives_user_month", "user_id", "month"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    progress: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    key_results: Mapped[list["OkrKeyResult"]] = relationship(
        back_populates="objective",
        cascade="all, delete-orphan",
    )
    comments: Mapped[list["OkrComment"]] = relationship(back_populates="objective")


class OkrKeyResult(Base, TimestampMixin, AuditMixin):
    """A key result under an objective.

    ``progress`` is a manual marker controlled by the UI slider. It is not
    derived from progress-update notes.
    """

    __tablename__ = "okr_key_results"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    objective_id: Mapped[int] = mapped_column(ForeignKey("okr_objectives.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    progress: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    objective: Mapped[OkrObjective] = relationship(back_populates="key_results")
    progress_updates: Mapped[list["OkrKeyResultProgress"]] = relationship(
        back_populates="key_result",
    )
    comments: Mapped[list["OkrComment"]] = relationship(back_populates="key_result")


class OkrKeyResultProgress(Base, TimestampMixin, AuditMixin):
    __tablename__ = "okr_key_result_progress"
    __table_args__ = (
        Index("ix_okr_kr_progress_kr_date", "key_result_id", "progress_date"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    key_result_id: Mapped[int] = mapped_column(ForeignKey("okr_key_results.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    progress_date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str] = mapped_column(Text, nullable=False)

    key_result: Mapped[OkrKeyResult] = relationship(back_populates="progress_updates")


class OkrComment(Base, TimestampMixin, AuditMixin):
    __tablename__ = "okr_comments"
    __table_args__ = (
        CheckConstraint(
            "(objective_id IS NOT NULL AND key_result_id IS NULL) OR "
            "(objective_id IS NULL AND key_result_id IS NOT NULL)",
            name="exactly_one_target",
        ),
        Index("ix_okr_comments_objective", "objective_id"),
        Index("ix_okr_comments_key_result", "key_result_id"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    objective_id: Mapped[int | None] = mapped_column(ForeignKey("okr_objectives.id"), nullable=True)
    key_result_id: Mapped[int | None] = mapped_column(ForeignKey("okr_key_results.id"), nullable=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    objective: Mapped[OkrObjective | None] = relationship(back_populates="comments")
    key_result: Mapped[OkrKeyResult | None] = relationship(back_populates="comments")
    author: Mapped["User"] = relationship()


class MonthlyReportSection(Base, TimestampMixin, AuditMixin):
    """One editable rich-text section of a user's monthly report.

    Two default sections per month: ``performance`` (业绩相关) and
    ``innovation`` (本月创新). Stored as sanitized HTML plus a TipTap JSON
    structure, same convention as problem/solution rich text.
    """

    __tablename__ = "monthly_report_sections"
    __table_args__ = (
        UniqueConstraint("user_id", "month", "section_key", name="uq_monthly_report_section"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    month: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    section_key: Mapped[str] = mapped_column(String(50), nullable=False)  # performance/innovation
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
