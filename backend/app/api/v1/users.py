from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import GroupBrief, UserBrief
from app.services.user_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=list[UserBrief])
def list_users(
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[User]:
    # Directory for collaborator / dispatch / metric-member pickers.
    return UserService(db).list_active(q=q)


@router.get("/groups", response_model=list[GroupBrief])
def list_user_groups(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[dict]:
    # 人员组目录：派发/成员选择器把组展开成成员 user_id。
    return UserService(db).list_groups()
