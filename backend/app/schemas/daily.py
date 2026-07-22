from datetime import date, datetime, time
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.schemas.common import ORMModel
from app.schemas.user import UserBrief

REPEAT_RULES = {"none", "daily", "weekly"}


class DailyTaskOut(ORMModel):
    id: int
    report_id: int
    user_id: int
    task_time: time
    content: str
    note: str | None = None
    is_private: bool = False
    is_done: bool
    done_at: datetime | None
    repeat_rule: str
    source: str
    assigned_to: int | None
    assigned_by: int | None
    sort_order: int
    collaborators: list[UserBrief] = []
    permission: str = "owner"
    can_edit: bool = True
    can_delete: bool = True
    can_toggle_done: bool = True
    can_manage_members: bool = True


class ProblemSolutionOut(ORMModel):
    id: int
    report_id: int
    user_id: int
    problem_text: str
    solution_html: str | None
    solution_json: dict | list | None
    search_text: str | None
    sort_order: int


class DailyReportOut(BaseModel):
    id: int | None
    user_id: int
    report_date: date
    status: str
    tasks: list[DailyTaskOut]
    problems: list[ProblemSolutionOut]


class DailyRangeDayOut(BaseModel):
    date: date
    tasks: list[DailyTaskOut]


class WeekDayOut(BaseModel):
    date: date
    has_content: bool


class DailyTaskCreate(BaseModel):
    date: date
    task_time: time
    content: str = Field(min_length=1)
    note: str | None = Field(default=None, max_length=2000)
    is_private: bool = False
    repeat_rule: str = "none"
    collaborator_ids: list[int] = Field(default_factory=list)
    # 派发目标：可为多人（前端把「人员组」展开成成员）。为空=不派发（落到自己）。
    # 派发给多人时为每人各建一份任务（沿用「派发即转移所有权」模型）。
    assigned_to_ids: list[int] = Field(default_factory=list)

    @field_validator("task_time")
    @classmethod
    def validate_task_time(cls, value: time) -> time:
        if value.minute % 5 != 0 or value.second != 0 or value.microsecond != 0:
            raise ValueError("task_time minute must be one of 00/05/.../55")
        return value

    @field_validator("repeat_rule")
    @classmethod
    def validate_repeat_rule(cls, value: str) -> str:
        if value not in REPEAT_RULES:
            raise ValueError("repeat_rule must be none/daily/weekly")
        return value


class DailyTaskUpdate(BaseModel):
    task_time: time | None = None
    content: str | None = Field(default=None, min_length=1)
    # "" clears the note; None leaves it unchanged.
    note: str | None = Field(default=None, max_length=2000)
    sort_order: int | None = None
    repeat_rule: str | None = None
    collaborator_ids: list[int] | None = None
    assigned_to_ids: list[int] | None = None
    is_private: bool | None = None

    @field_validator("task_time")
    @classmethod
    def validate_task_time(cls, value: time | None) -> time | None:
        if value is not None and (value.minute % 5 != 0 or value.second != 0 or value.microsecond != 0):
            raise ValueError("task_time minute must be one of 00/05/.../55")
        return value

    @field_validator("repeat_rule")
    @classmethod
    def validate_repeat_rule(cls, value: str | None) -> str | None:
        if value is not None and value not in REPEAT_RULES:
            raise ValueError("repeat_rule must be none/daily/weekly")
        return value


class DailyTaskDoneIn(BaseModel):
    is_done: bool


class ProblemSolutionCreate(BaseModel):
    date: date
    problem_text: str = Field(min_length=1)
    solution_html: str | None = ""
    solution_json: dict[str, Any] | list[Any] | None = None


class ProblemSolutionUpdate(BaseModel):
    problem_text: str | None = Field(default=None, min_length=1)
    solution_html: str | None = None
    solution_json: dict[str, Any] | list[Any] | None = None
    sort_order: int | None = None
