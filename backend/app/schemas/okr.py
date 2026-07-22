from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import ORMModel

_MONTH_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
_SECTION_KEYS = {"performance", "innovation"}


def _validate_month(value: str) -> str:
    if not _MONTH_RE.match(value):
        raise ValueError("month must be YYYY-MM")
    return value


# ---- key results ---------------------------------------------------------


class KeyResultCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=300)
    progress: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class KeyResultUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=300)
    progress: Decimal | None = Field(default=None, ge=0, le=100)


class OkrOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ids: list[int] = Field(min_length=1)


class KeyResultProgressCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: str = Field(min_length=1, max_length=4000)
    progress_date: date

    @field_validator("note")
    @classmethod
    def validate_note(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("note cannot be blank")
        return value


class KeyResultProgressOut(ORMModel):
    id: int
    key_result_id: int
    user_id: int
    note: str
    progress_date: date
    created_at: datetime


class KeyResultOut(ORMModel):
    id: int
    objective_id: int
    title: str
    progress: Decimal  # 0..100, manually marked by the KR slider
    sort_order: int
    comment_count: int = 0
    progress_updates: list[KeyResultProgressOut] = []


# ---- objectives ----------------------------------------------------------


class ObjectiveCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    month: str
    title: str = Field(min_length=1, max_length=300)
    key_results: list[KeyResultCreate] = Field(default_factory=list)

    @field_validator("month")
    @classmethod
    def validate_month(cls, value: str) -> str:
        return _validate_month(value)


class ObjectiveUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=1, max_length=300)


class OkrCommentCreate(BaseModel):
    content: str = Field(min_length=1, max_length=4000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("content cannot be blank")
        return value


class OkrCommentUpdate(OkrCommentCreate):
    pass


class OkrCommentAuthorOut(BaseModel):
    id: int
    name: str
    avatar_url: str | None


class OkrCommentOut(BaseModel):
    id: int
    objective_id: int | None
    key_result_id: int | None
    content: str
    author: OkrCommentAuthorOut
    created_at: datetime
    updated_at: datetime
    can_edit: bool


class ObjectiveOut(ORMModel):
    id: int
    user_id: int
    month: str
    title: str
    progress: Decimal
    sort_order: int
    comment_count: int = 0
    key_results: list[KeyResultOut] = []


# ---- monthly report ------------------------------------------------------


class MonthlyReportSectionOut(ORMModel):
    id: int
    month: str
    section_key: str
    title: str
    content_html: str | None
    content_json: str | None
    sort_order: int


class MonthlyReportSectionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=100)
    content_html: str | None = None
    content_json: str | None = None


# ---- month aggregate + AI review -----------------------------------------


class OkrReviewOut(BaseModel):
    """Lightweight whole-set OKR review summary."""

    status: str = "empty"  # empty | ready
    generated_at: str | None = None
    quality_score: Decimal | None = None
    summary: str | None = None


class OkrMonthOut(BaseModel):
    month: str
    objectives: list[ObjectiveOut]
    monthly_report: list[MonthlyReportSectionOut]
    review: OkrReviewOut
