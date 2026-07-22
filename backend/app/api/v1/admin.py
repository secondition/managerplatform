from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, require_permission
from app.core.permissions import ADMIN_DEPARTMENT, ADMIN_EMPLOYEE
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import (
    ContactSyncOut,
    ContactSyncLogOut,
    DepartmentCreate,
    DepartmentOut,
    DepartmentUpdate,
    EmployeeOut,
    EmployeeUpdate,
    PermissionsIn,
    StatusIn,
)
from app.services.admin_service import AdminService
from app.services.feishu_contact_service import FeishuContactService
from app.models.org import ContactSyncLog

router = APIRouter(prefix="/admin", tags=["admin"])


# ---- Employees ----


@router.get("/employees", response_model=list[EmployeeOut])
def list_employees(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_EMPLOYEE)),
) -> list[dict]:
    return AdminService(db, user).list_employees()


@router.patch("/employees/{user_id}", response_model=EmployeeOut, dependencies=[Depends(csrf_protect)])
def update_employee(
    user_id: int,
    payload: EmployeeUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_EMPLOYEE)),
) -> dict:
    return AdminService(db, user).update_employee(user_id, payload)


@router.post(
    "/employees/{user_id}/permissions",
    response_model=EmployeeOut,
    dependencies=[Depends(csrf_protect)],
)
def set_permissions(
    user_id: int,
    payload: PermissionsIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_EMPLOYEE)),
) -> dict:
    return AdminService(db, user).set_permissions(user_id, payload.permissions)


@router.post(
    "/employees/{user_id}/status",
    response_model=EmployeeOut,
    dependencies=[Depends(csrf_protect)],
)
def set_status(
    user_id: int,
    payload: StatusIn,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_EMPLOYEE)),
) -> dict:
    return AdminService(db, user).set_status(user_id, payload.status)


@router.delete(
    "/employees/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(csrf_protect)],
)
def delete_employee(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_EMPLOYEE)),
) -> Response:
    AdminService(db, user).delete_employee(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/feishu/sync-contacts",
    response_model=ContactSyncOut,
    dependencies=[Depends(csrf_protect)],
)
async def sync_feishu_contacts(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_EMPLOYEE)),
):
    return await FeishuContactService(db, user).sync_contacts()


@router.get("/feishu/sync-logs", response_model=list[ContactSyncLogOut])
def list_feishu_contact_sync_logs(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_EMPLOYEE)),
) -> list[ContactSyncLog]:
    del user
    return list(
        db.scalars(
            select(ContactSyncLog)
            .where(ContactSyncLog.deleted_at.is_(None))
            .order_by(ContactSyncLog.started_at.desc(), ContactSyncLog.id.desc())
            .limit(limit)
        ).all()
    )


# ---- Departments ----


@router.get("/departments", response_model=list[DepartmentOut])
def list_departments(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_DEPARTMENT)),
) -> list:
    return AdminService(db, user).list_departments()


@router.post("/departments", response_model=DepartmentOut, dependencies=[Depends(csrf_protect)])
def create_department(
    payload: DepartmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_DEPARTMENT)),
):
    return AdminService(db, user).create_department(payload)


@router.patch("/departments/{dept_id}", response_model=DepartmentOut, dependencies=[Depends(csrf_protect)])
def update_department(
    dept_id: int,
    payload: DepartmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_DEPARTMENT)),
):
    return AdminService(db, user).update_department(dept_id, payload)


@router.delete(
    "/departments/{dept_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(csrf_protect)],
)
def delete_department(
    dept_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_DEPARTMENT)),
) -> Response:
    AdminService(db, user).delete_department(dept_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)

