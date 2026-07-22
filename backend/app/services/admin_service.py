from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.org import Department, Group, GroupMember
from app.models.user import User, UserPermission
from app.schemas.admin import (
    DepartmentCreate,
    DepartmentUpdate,
    EmployeeUpdate,
    GroupCreate,
    GroupUpdate,
)
from app.services.session_service import revoke_user_refresh_tokens
from app.core.security import utcnow


class AdminService:
    def __init__(self, db: Session, actor: User) -> None:
        self.db = db
        self.actor = actor

    # ---- Employees ----

    def list_employees(self) -> list[dict]:
        users = self.db.scalars(
            select(User).where(User.deleted_at.is_(None)).order_by(User.name, User.id)
        ).all()
        return [self._serialize_employee(user) for user in users]

    def update_employee(self, user_id: int, payload: EmployeeUpdate) -> dict:
        user = self._get_user(user_id)
        for field in ("name", "email", "department_id"):
            if field not in payload.model_fields_set:
                continue
            value = getattr(payload, field)
            if field == "name" and value is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field} cannot be null",
                )
            setattr(user, field, value.strip() if isinstance(value, str) else value)
        user.updated_by = self.actor.id
        self.db.commit()
        self.db.refresh(user)
        return self._serialize_employee(user)

    def set_permissions(self, user_id: int, permissions: list[str]) -> dict:
        user = self._get_user(user_id)
        self._set_permissions(user, permissions)
        user.updated_by = self.actor.id
        self.db.commit()
        self.db.refresh(user)
        return self._serialize_employee(user)

    def set_status(self, user_id: int, new_status: str) -> dict:
        user = self._get_user(user_id)
        if user.role == "owner":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner cannot be disabled")
        if user.status != new_status:
            user.status = new_status
            if new_status == "disabled":
                user.token_version += 1
                revoke_user_refresh_tokens(self.db, user.id, self.actor.id)
            user.updated_by = self.actor.id
            self.db.commit()
            self.db.refresh(user)
        return self._serialize_employee(user)

    def delete_employee(self, user_id: int) -> None:
        user = self._get_user(user_id)
        if user.role == "owner":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Owner cannot be deleted")
        user.deleted_at = utcnow()
        user.token_version += 1
        revoke_user_refresh_tokens(self.db, user.id, self.actor.id)
        user.updated_by = self.actor.id
        self.db.commit()

    def _set_permissions(self, user: User, permissions: list[str]) -> None:
        existing = self.db.scalars(
            select(UserPermission).where(
                UserPermission.user_id == user.id,
                UserPermission.deleted_at.is_(None),
            )
        ).all()
        by_name = {row.permission: row for row in existing}
        wanted = set(permissions)
        for name, row in by_name.items():
            row.enabled = name in wanted
            row.updated_by = self.actor.id
        for name in wanted - set(by_name):
            self.db.add(
                UserPermission(
                    user_id=user.id,
                    permission=name,
                    enabled=True,
                    created_by=self.actor.id,
                    updated_by=self.actor.id,
                )
            )

    def _get_user(self, user_id: int) -> User:
        user = self.db.scalar(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        if user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Employee not found")
        return user

    def _serialize_employee(self, user: User) -> dict:
        permissions = self.db.scalars(
            select(UserPermission.permission).where(
                UserPermission.user_id == user.id,
                UserPermission.enabled.is_(True),
                UserPermission.deleted_at.is_(None),
            )
        ).all()
        return {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "avatar_url": user.avatar_url,
            "role": user.role,
            "department_id": user.department_id,
            "status": user.status,
            "last_login_at": user.last_login_at,
            "sync_source": user.sync_source,
            "last_synced_at": user.last_synced_at,
            "disabled_reason": user.disabled_reason,
            "permissions": list(permissions),
        }

    # ---- Departments ----

    def list_departments(self) -> list[Department]:
        return list(
            self.db.scalars(
                select(Department)
                .where(Department.deleted_at.is_(None))
                .order_by(Department.sort_order, Department.id)
            ).all()
        )

    def create_department(self, payload: DepartmentCreate) -> Department:
        dept = Department(
            name=payload.name.strip(),
            parent_id=payload.parent_id,
            sort_order=payload.sort_order,
            created_by=self.actor.id,
            updated_by=self.actor.id,
        )
        self.db.add(dept)
        self.db.commit()
        self.db.refresh(dept)
        return dept

    def update_department(self, dept_id: int, payload: DepartmentUpdate) -> Department:
        dept = self._get_department(dept_id)
        for field in ("name", "parent_id", "sort_order"):
            if field not in payload.model_fields_set:
                continue
            value = getattr(payload, field)
            if field in {"name", "sort_order"} and value is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field} cannot be null",
                )
            setattr(dept, field, value.strip() if isinstance(value, str) else value)
        dept.updated_by = self.actor.id
        self.db.commit()
        self.db.refresh(dept)
        return dept

    def delete_department(self, dept_id: int) -> None:
        dept = self._get_department(dept_id)
        dept.deleted_at = utcnow()
        dept.updated_by = self.actor.id
        self.db.commit()

    def _get_department(self, dept_id: int) -> Department:
        dept = self.db.scalar(
            select(Department).where(Department.id == dept_id, Department.deleted_at.is_(None))
        )
        if dept is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")
        return dept

    # ---- Groups ----

    def list_groups(self) -> list[dict]:
        groups = self.db.scalars(
            select(Group)
            .where(Group.deleted_at.is_(None))
            .order_by(Group.sort_order, Group.id)
        ).all()
        return [self._serialize_group(group) for group in groups]

    def create_group(self, payload: GroupCreate) -> dict:
        group = Group(
            name=payload.name.strip(),
            description=payload.description,
            source="manual",
            sort_order=payload.sort_order,
            created_by=self.actor.id,
            updated_by=self.actor.id,
        )
        self.db.add(group)
        self.db.flush()
        self._set_group_members(group, payload.member_ids)
        self.db.commit()
        self.db.refresh(group)
        return self._serialize_group(group)

    def update_group(self, group_id: int, payload: GroupUpdate) -> dict:
        group = self._get_group(group_id)
        for field in ("name", "description", "sort_order"):
            if field not in payload.model_fields_set:
                continue
            value = getattr(payload, field)
            if field in {"name", "sort_order"} and value is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"{field} cannot be null",
                )
            setattr(group, field, value.strip() if isinstance(value, str) else value)
        group.updated_by = self.actor.id
        self.db.commit()
        self.db.refresh(group)
        return self._serialize_group(group)

    def set_group_members(self, group_id: int, member_ids: list[int]) -> dict:
        group = self._get_group(group_id)
        self._set_group_members(group, member_ids)
        group.updated_by = self.actor.id
        self.db.commit()
        self.db.refresh(group)
        return self._serialize_group(group)

    def delete_group(self, group_id: int) -> None:
        group = self._get_group(group_id)
        group.deleted_at = utcnow()
        group.updated_by = self.actor.id
        self.db.commit()

    def create_group_from_department(self, dept_id: int, name: str | None) -> dict:
        """从部门当前成员建组（一次性快照）：导入后与部门解耦。"""
        dept = self._get_department(dept_id)
        member_ids = list(
            self.db.scalars(
                select(User.id).where(
                    User.department_id == dept_id, User.deleted_at.is_(None)
                )
            ).all()
        )
        group = Group(
            name=(name.strip() if name else dept.name),
            description=None,
            source="department",
            sort_order=0,
            created_by=self.actor.id,
            updated_by=self.actor.id,
        )
        self.db.add(group)
        self.db.flush()
        self._set_group_members(group, member_ids)
        self.db.commit()
        self.db.refresh(group)
        return self._serialize_group(group)

    def _set_group_members(self, group: Group, member_ids: list[int]) -> None:
        wanted = set(member_ids)
        if wanted:
            valid = set(
                self.db.scalars(
                    select(User.id).where(User.id.in_(wanted), User.deleted_at.is_(None))
                ).all()
            )
            invalid = wanted - valid
            if invalid:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"unknown users: {sorted(invalid)}",
                )
        existing = {row.user_id: row for row in group.members}
        for user_id, row in list(existing.items()):
            if user_id not in wanted:
                self.db.delete(row)
        for user_id in wanted - set(existing):
            self.db.add(
                GroupMember(
                    group_id=group.id,
                    user_id=user_id,
                    created_by=self.actor.id,
                    updated_by=self.actor.id,
                )
            )

    def _get_group(self, group_id: int) -> Group:
        group = self.db.scalar(
            select(Group).where(Group.id == group_id, Group.deleted_at.is_(None))
        )
        if group is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
        return group

    def _serialize_group(self, group: Group) -> dict:
        member_ids = list(
            self.db.scalars(
                select(GroupMember.user_id).where(GroupMember.group_id == group.id)
            ).all()
        )
        return {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "source": group.source,
            "sort_order": group.sort_order,
            "member_ids": member_ids,
        }

