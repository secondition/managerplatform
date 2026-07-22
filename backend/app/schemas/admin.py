from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.core.permissions import ASSIGNABLE_PERMISSIONS
from app.schemas.common import ORMModel


class EmployeeOut(ORMModel):
    id: int
    name: str
    email: str | None
    avatar_url: str | None
    role: str
    department_id: int | None
    status: str
    last_login_at: datetime | None
    sync_source: str
    last_synced_at: datetime | None
    disabled_reason: str | None
    permissions: list[str]


class EmployeeUpdate(BaseModel):
    # Role is no longer assignable: only owner/member remain, and owner is
    # reserved for OWNER_FEISHU_UNION_ID bootstrap. Access is controlled by
    # permission rows, not by role=admin.
    name: str | None = Field(default=None, min_length=1, max_length=80)
    email: str | None = Field(default=None, max_length=120)
    department_id: int | None = None


class PermissionsIn(BaseModel):
    permissions: list[str]

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: list[str]) -> list[str]:
        invalid = [item for item in value if item not in ASSIGNABLE_PERMISSIONS]
        if invalid:
            raise ValueError(f"unknown permissions: {invalid}")
        return value


class StatusIn(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        if value not in {"active", "disabled"}:
            raise ValueError("status must be active/disabled")
        return value


class DepartmentOut(ORMModel):
    id: int
    name: str
    parent_id: int | None
    feishu_department_id: str | None
    sort_order: int
    last_synced_at: datetime | None


class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: int | None = None
    sort_order: int = 0


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: int | None = None
    sort_order: int | None = None


class GroupOut(ORMModel):
    id: int
    name: str
    description: str | None
    source: str
    sort_order: int
    member_ids: list[int] = []


class GroupCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    sort_order: int = 0
    member_ids: list[int] = Field(default_factory=list)


class GroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    sort_order: int | None = None


class GroupMembersIn(BaseModel):
    member_ids: list[int]


class GroupFromDepartmentIn(BaseModel):
    department_id: int
    name: str | None = Field(default=None, max_length=100)


class GroupImportSourceOut(BaseModel):
    """Slim department entry for the group page's "import from department" list —
    readable with feature:group, so it doesn't require admin:department."""

    id: int
    name: str


class ContactSyncOut(BaseModel):
    created: int
    updated: int
    disabled: int
    skipped: int
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None = None


class ContactSyncLogOut(ORMModel):
    id: int
    status: str
    started_at: datetime
    finished_at: datetime | None
    created_count: int
    updated_count: int
    disabled_count: int
    skipped_count: int
    error_message: str | None = None


class CompanySettingOut(ORMModel):
    company_name: str
    logo_url: str | None
    footer_text: str


class CompanySettingUpdate(BaseModel):
    company_name: str = Field(min_length=1, max_length=100)
    footer_text: str = Field(min_length=1, max_length=200)
