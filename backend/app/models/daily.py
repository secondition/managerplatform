from datetime import date, datetime, time

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    Time,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.db.types import BigInt, JSONText


class DailyReport(Base, TimestampMixin, AuditMixin):
    __tablename__ = "daily_reports"
    __table_args__ = (
        Index(
            "uq_daily_reports_user_date_active",
            "user_id",
            "report_date",
            unique=True,
            sqlite_where=text("deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    report_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="draft", nullable=False)

    tasks: Mapped[list["DailyTask"]] = relationship(back_populates="report")
    problems: Mapped[list["ProblemSolution"]] = relationship(back_populates="report")


class DailyTask(Base, TimestampMixin, AuditMixin):
    __tablename__ = "daily_tasks"
    __table_args__ = (
        Index("ix_daily_tasks_report_sort", "report_id", "sort_order"),
        Index(
            "uq_daily_tasks_repeat_series_report_active",
            "repeat_series_id",
            "report_id",
            unique=True,
            sqlite_where=text("repeat_series_id IS NOT NULL AND deleted_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("daily_reports.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    task_time: Mapped[time] = mapped_column(Time, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Employee annotation: "虽不在OKR但重要，原因是___" — fed to the daily-score
    # engine as the user_notes variable so it doesn't misjudge OKR-outside work.
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    repeat_rule: Mapped[str] = mapped_column(String(50), default="none", nullable=False)
    repeat_series_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)
    assigned_to: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    report: Mapped[DailyReport] = relationship(back_populates="tasks")
    collaborators: Mapped[list["DailyTaskCollaborator"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
    )


class DailyTaskCollaborator(Base, TimestampMixin, AuditMixin):
    __tablename__ = "daily_task_collaborators"
    __table_args__ = (
        UniqueConstraint("task_id", "user_id", name="uq_daily_task_collaborators_task_user"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("daily_tasks.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    task: Mapped[DailyTask] = relationship(back_populates="collaborators")


class ProblemSolution(Base, TimestampMixin, AuditMixin):
    __tablename__ = "problem_solutions"
    __table_args__ = (Index("ix_problem_solutions_report_sort", "report_id", "sort_order"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("daily_reports.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    problem_text: Mapped[str] = mapped_column(Text, nullable=False)
    solution_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    solution_json: Mapped[dict | list | None] = mapped_column(JSONText, nullable=True)
    search_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    report: Mapped[DailyReport] = relationship(back_populates="problems")
