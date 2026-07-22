from datetime import datetime

from app.schemas.common import ORMModel


class UserBrief(ORMModel):
    id: int
    name: str
    avatar_url: str | None
    department_id: int | None


class UserOut(ORMModel):
    id: int
    name: str
    email: str | None
    avatar_url: str | None
    role: str
    department_id: int | None
    status: str
    last_login_at: datetime | None


class GroupBrief(ORMModel):
    id: int
    name: str
    member_ids: list[int]


class AuthUserResponse(ORMModel):
    user: UserOut
    permissions: list[str]
    csrf_token: str | None = None
