from datetime import date
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import AuditMixin, Base, TimestampMixin
from app.db.types import BigInt


class TrafficMetric(Base, TimestampMixin, AuditMixin):
    """A shared definition for a long-lived weekly traffic-light metric.

    Every assignee receives an independent assignment with its own weekly values.
    The name, direction and targets stay centralized on this definition.
    """

    __tablename__ = "traffic_metrics"
    __table_args__ = (Index("ix_traffic_metrics_owner", "owner_id"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # increase = 越高越好(≥目标绿); decrease = 越低越好(≤目标绿)。
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    weekly_target: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    north_star_target: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    values: Mapped[list["TrafficMetricValue"]] = relationship(
        back_populates="metric",
        cascade="all, delete-orphan",
    )
    members: Mapped[list["TrafficMetricMember"]] = relationship(
        back_populates="metric",
        cascade="all, delete-orphan",
    )
    assignments: Mapped[list["TrafficMetricAssignment"]] = relationship(
        back_populates="metric",
        cascade="all, delete-orphan",
    )


class TrafficMetricAssignment(Base, TimestampMixin, AuditMixin):
    __tablename__ = "traffic_metric_assignments"
    __table_args__ = (
        UniqueConstraint("metric_id", "assignee_id", name="uq_metric_assignee"),
        Index("ix_traffic_metric_assignments_assignee", "assignee_id"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("traffic_metrics.id"), nullable=False)
    assignee_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    assigned_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    metric: Mapped[TrafficMetric] = relationship(back_populates="assignments")
    assignee = relationship("User", foreign_keys=[assignee_id])
    assigned_by = relationship("User", foreign_keys=[assigned_by_id])
    values: Mapped[list["TrafficMetricValue"]] = relationship(
        back_populates="assignment",
        cascade="all, delete-orphan",
    )


class TrafficMetricMember(Base, TimestampMixin, AuditMixin):
    __tablename__ = "traffic_metric_members"
    __table_args__ = (UniqueConstraint("metric_id", "user_id", name="uq_metric_member"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("traffic_metrics.id"), nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default="viewer", nullable=False)

    metric: Mapped[TrafficMetric] = relationship(back_populates="members")
    user = relationship("User")


class TrafficMetricValue(Base, TimestampMixin, AuditMixin):
    """One filled value for an assignment in a given ISO week (Monday-start)."""

    __tablename__ = "traffic_metric_values"
    __table_args__ = (
        UniqueConstraint("assignment_id", "week_start", name="uq_metric_assignment_week"),
        Index("ix_traffic_metric_values_metric_week", "metric_id", "week_start"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True)
    metric_id: Mapped[int] = mapped_column(ForeignKey("traffic_metrics.id"), nullable=False)
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("traffic_metric_assignments.id"), nullable=False
    )
    week_start: Mapped[date] = mapped_column(Date, nullable=False)
    week_end: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="missed", nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    metric: Mapped[TrafficMetric] = relationship(back_populates="values")
    assignment: Mapped[TrafficMetricAssignment] = relationship(back_populates="values")
