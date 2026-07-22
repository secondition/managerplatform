"""人员组 (people groups) — a company-wide shared variable pool.

Moved out of the admin backend: any employee holding the ``feature:group``
permission may view and edit groups. Group members are consumed
by dispatch / member pickers via ``/users/groups`` (open to all active users).
"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, require_permission
from app.core.permissions import FEATURE_GROUP
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import (
    GroupCreate,
    GroupFromDepartmentIn,
    GroupImportSourceOut,
    GroupMembersIn,
    GroupOut,
    GroupUpdate,
)
from app.services.admin_service import AdminService

router = APIRouter(prefix="/groups", tags=["groups"])


@router.get("", response_model=list[GroupOut])
def list_groups(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_GROUP)),
) -> list:
    return AdminService(db, user).list_groups()


@router.get("/import-sources", response_model=list[GroupImportSourceOut])
def list_import_sources(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_GROUP)),
) -> list:
    # Departments as import candidates — id+name only, no admin:department needed.
    return [
        GroupImportSourceOut(id=d.id, name=d.name)
        for d in AdminService(db, user).list_departments()
    ]


@router.post("", response_model=GroupOut, dependencies=[Depends(csrf_protect)])
def create_group(
    payload: GroupCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_GROUP)),
):
    return AdminService(db, user).create_group(payload)


@router.post(
    "/from-department",
    response_model=GroupOut,
    dependencies=[Depends(csrf_protect)],
)
def create_group_from_department(
    payload: GroupFromDepartmentIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_GROUP)),
):
    return AdminService(db, user).create_group_from_department(payload.department_id, payload.name)


@router.patch("/{group_id}", response_model=GroupOut, dependencies=[Depends(csrf_protect)])
def update_group(
    group_id: int,
    payload: GroupUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_GROUP)),
):
    return AdminService(db, user).update_group(group_id, payload)


@router.post(
    "/{group_id}/members",
    response_model=GroupOut,
    dependencies=[Depends(csrf_protect)],
)
def set_group_members(
    group_id: int,
    payload: GroupMembersIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_GROUP)),
):
    return AdminService(db, user).set_group_members(group_id, payload.member_ids)


@router.delete(
    "/{group_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(csrf_protect)],
)
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(FEATURE_GROUP)),
) -> Response:
    AdminService(db, user).delete_group(group_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
