from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.org import Group, GroupMember
from app.models.user import User


class UserService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active(self, q: str | None = None, limit: int = 50) -> list[User]:
        stmt = select(User).where(User.status == "active", User.deleted_at.is_(None))
        if q:
            like = f"%{q.strip()}%"
            stmt = stmt.where(User.name.ilike(like))
        stmt = stmt.order_by(User.name, User.id).limit(limit)
        return list(self.db.scalars(stmt).all())

    def list_groups(self) -> list[dict]:
        """人员组目录，供派发/成员选择器把组展开成成员。仅返回有成员的活跃组。"""
        groups = self.db.scalars(
            select(Group)
            .where(Group.deleted_at.is_(None))
            .order_by(Group.sort_order, Group.id)
        ).all()
        result: list[dict] = []
        for group in groups:
            member_ids = list(
                self.db.scalars(
                    select(GroupMember.user_id).where(GroupMember.group_id == group.id)
                ).all()
            )
            result.append({"id": group.id, "name": group.name, "member_ids": member_ids})
        return result
