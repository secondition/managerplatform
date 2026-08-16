from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ORMModel

_DIRECTIONS = {"increase", "decrease"}


class WeekColumnOut(BaseModel):
    week_index: int  # ISO week number, used as the column label key
    label: str
    week_start: date
    week_end: date
    is_empty: bool = False


class TrafficMetricValueOut(ORMModel):
    id: int
    metric_id: int
    assignment_id: int
    week_start: date
    week_end: date
    value: Decimal | None
    status: str  # on_target | missed
    note: str | None


class TrafficMetricMemberOut(BaseModel):
    user_id: int
    name: str
    avatar_url: str | None
    role: str


class TrafficMetricAssigneeOut(BaseModel):
    assignment_id: int
    user_id: int
    name: str
    avatar_url: str | None
    effective_from: date


class TrafficMetricOut(ORMModel):
    id: int
    assignment_id: int | None = None
    owner_id: int
    assignee: TrafficMetricAssigneeOut | None = None
    name: str
    unit: str | None
    direction: str
    weekly_target: Decimal | None
    north_star_target: Decimal | None
    sort_order: int
    values: list[TrafficMetricValueOut]  # only weeks inside the current window
    recent_avg: Decimal | None  # mean of filled values in the window
    status: str  # rollup for the current window: on_target | missed | empty
    members: list[TrafficMetricMemberOut] = []
    assignees: list[TrafficMetricAssigneeOut] = []
    my_role: str = "owner"
    can_edit_values: bool = True
    can_edit_meta: bool = True
    can_manage_members: bool = True
    can_delete: bool = True
    is_pending: bool = False  # newest window week not yet filled and I can fill


def _validate_direction(value: str | None) -> str | None:
    if value is not None and value not in _DIRECTIONS:
        raise ValueError("direction must be increase/decrease")
    return value


def _validate_name(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        raise ValueError("name cannot be blank")
    return normalized


class TrafficMetricCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    unit: str | None = Field(default=None, max_length=30)
    direction: str = "increase"
    weekly_target: Decimal | None = None
    north_star_target: Decimal | None = None
    editor_ids: list[int] = Field(default_factory=list)
    viewer_ids: list[int] = Field(default_factory=list)

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, value: str) -> str:
        return _validate_direction(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _validate_name(value)


class TrafficMetricUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    unit: str | None = Field(default=None, max_length=30)
    direction: str | None = None
    weekly_target: Decimal | None = None
    north_star_target: Decimal | None = None
    sort_order: int | None = None
    editor_ids: list[int] | None = None
    viewer_ids: list[int] | None = None

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, value: str | None) -> str | None:
        return _validate_direction(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        return _validate_name(value)


class TrafficMetricValueUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Per-week status is computed server-side from the value vs. weekly target;
    # the client no longer picks the traffic-light color manually.
    value: Decimal | None = None
    note: str | None = None
