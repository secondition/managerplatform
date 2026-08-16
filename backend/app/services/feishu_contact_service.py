from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.permissions import DEFAULT_FEATURE_PERMISSIONS
from app.core.security import utcnow
from app.models.org import ContactSyncLog, Department
from app.models.user import User, UserPermission
from app.services.session_service import revoke_user_refresh_tokens


@dataclass(frozen=True)
class FeishuDepartment:
    feishu_department_id: str
    name: str
    parent_feishu_department_id: str | None = None


@dataclass(frozen=True)
class FeishuContactUser:
    union_id: str
    open_id: str
    user_id: str | None
    name: str
    email: str | None
    avatar_url: str | None
    department_ids: list[str]
    message_receive_id: str
    message_receive_id_type: str


@dataclass
class ContactSyncResult:
    created: int = 0
    updated: int = 0
    disabled: int = 0
    skipped: int = 0
    status: str = "succeeded"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None


class FeishuContactService:
    _tenant_token: str | None = None
    _tenant_token_expires_at: datetime | None = None

    def __init__(self, db: Session, actor: User) -> None:
        self.db = db
        self.actor = actor

    async def sync_contacts(self) -> ContactSyncResult:
        started_at = utcnow()
        log = ContactSyncLog(started_at=started_at, status="running", created_by=self.actor.id, updated_by=self.actor.id)
        self.db.add(log)
        self.db.commit()
        log_id = log.id  # 存普通变量：rollback 后再从 log 对象取属性会触发重载
        result = ContactSyncResult(started_at=started_at)
        try:
            departments = await self._fetch_departments()
            users = await self._fetch_users(departments)
            dept_map = self._upsert_departments(departments)
            result.created, result.updated, result.skipped = self._upsert_users(users, dept_map)
            result.disabled = self._disable_missing_users({u.union_id for u in users if u.union_id})
            result.finished_at = utcnow()
            self._finish_log(log_id, result)
            return result
        except Exception as exc:
            # flush 失败会让 session 进入需要 rollback 的状态；不先 rollback，
            # 下面 _finish_log 读 log 会触发 PendingRollbackError 掩盖真实原因。
            self.db.rollback()
            result.status = "failed"
            result.finished_at = utcnow()
            result.error_message = str(exc)[:1000]
            self._finish_log(log_id, result)
            raise

    async def _fetch_departments(self) -> list[FeishuDepartment]:
        # 飞书 /children + fetch_child=true 会返回扁平列表且每项 parent_department_id 恒为 null，
        # 拿不到父子关系。改逐层 BFS：只查「直接子部门」，父 id = 当前正在查询的部门。
        departments: list[FeishuDepartment] = []
        seen: set[str] = set()
        queue: list[str] = ["0"]  # 从根开始，逐层查直接子部门
        while queue:
            parent_id = queue.pop(0)
            data_items = await self._paged_get(
                f"{settings.feishu_contact_dept_path}/{parent_id}/children",
                params={"page_size": 50, "department_id_type": "open_department_id"},
            )
            for item in data_items:
                dept_id = self._string_field(item, "open_department_id", "department_id", "id")
                if not dept_id or dept_id == "0" or dept_id in seen:
                    continue
                seen.add(dept_id)
                name = self._name_field(item.get("name")) or self._string_field(item, "department_name") or dept_id
                # 父 = 当前遍历的 parent_id；根的直接子部门父记为 None（不是 "0"）。
                departments.append(
                    FeishuDepartment(
                        feishu_department_id=dept_id,
                        name=name,
                        parent_feishu_department_id=parent_id if parent_id != "0" else None,
                    )
                )
                queue.append(dept_id)  # 入队继续下钻子部门
        return departments

    async def _fetch_users(self, departments: list[FeishuDepartment]) -> list[FeishuContactUser]:
        # 飞书按部门查人只返回该部门「直属」成员，不含子部门，所以要逐部门查。
        # 飞书 /users 精简返回不含 department_ids，归属只能由「从哪个部门查到的」决定；
        # 一个人可属于多个部门，故累加每人的全部真实部门 id（"0" 根不算真实部门）。
        # "0" 兜底捞根直属成员（如未分配部门的 owner）。
        department_ids = [d.feishu_department_id for d in departments]
        department_ids.append("0")
        users_by_union: dict[str, FeishuContactUser] = {}
        depts_by_union: dict[str, list[str]] = {}
        for dept_id in department_ids:
            items = await self._paged_get(
                settings.feishu_contact_user_path,
                params={"department_id": dept_id, "page_size": 50, "department_id_type": "open_department_id"},
            )
            for item in items:
                user = self._normalize_user(item)
                if user is None:
                    continue
                users_by_union.setdefault(user.union_id, user)  # 基础信息首见即取
                if dept_id != "0":  # 累加真实部门归属，保留发现顺序、去重
                    bucket = depts_by_union.setdefault(user.union_id, [])
                    if dept_id not in bucket:
                        bucket.append(dept_id)
        # 用汇总的部门集合覆盖每个用户的 department_ids
        return [
            replace(user, department_ids=depts_by_union.get(union_id, []))
            for union_id, user in users_by_union.items()
        ]

    def _normalize_user(self, item: dict[str, Any]) -> FeishuContactUser | None:
        union_id = self._string_field(item, "union_id")
        if not union_id:
            return None
        actual_open_id = self._string_field(item, "open_id")
        actual_user_id = self._string_field(item, "user_id")
        open_id = actual_open_id or actual_user_id or union_id
        if actual_open_id:
            message_receive_id, message_receive_id_type = actual_open_id, "open_id"
        elif actual_user_id:
            message_receive_id, message_receive_id_type = actual_user_id, "user_id"
        else:
            message_receive_id, message_receive_id_type = union_id, "union_id"
        name = self._name_field(item.get("name")) or self._string_field(item, "name", "en_name") or "未命名员工"
        avatar = item.get("avatar")
        avatar_url = self._string_field(item, "avatar_url")
        if not avatar_url and isinstance(avatar, dict):
            avatar_url = self._string_field(avatar, "avatar_url", "thumb", "middle", "big")
        # 飞书 /users 精简返回通常不含 department_ids；归属由 _fetch_users 汇总覆盖。
        # 这里保留解析：万一返回带了该字段也不丢。
        departments = item.get("department_ids") or item.get("department_id") or []
        if isinstance(departments, str):
            department_ids = [departments]
        elif isinstance(departments, list):
            department_ids = [str(x) for x in departments if x]
        else:
            department_ids = []
        return FeishuContactUser(
            union_id=union_id,
            open_id=open_id,
            user_id=actual_user_id,
            name=name,
            email=self._string_field(item, "email"),
            avatar_url=avatar_url,
            department_ids=department_ids,
            message_receive_id=message_receive_id,
            message_receive_id_type=message_receive_id_type,
        )

    async def _paged_get(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        token = await self._tenant_access_token()
        items: list[dict[str, Any]] = []
        page_token: str | None = None
        async with httpx.AsyncClient(base_url=settings.feishu_api_base, timeout=20.0) as client:
            while True:
                query = dict(params)
                if page_token:
                    query["page_token"] = page_token
                resp = await client.get(path, params=query, headers={"Authorization": f"Bearer {token}"})
                data = self._checked_feishu_response(resp)
                batch = data.get("items") or data.get("departments") or data.get("users") or []
                if isinstance(batch, list):
                    items.extend([item for item in batch if isinstance(item, dict)])
                if not data.get("has_more"):
                    break
                page_token = data.get("page_token")
                if not page_token:
                    break
        return items

    async def _tenant_access_token(self) -> str:
        now = utcnow()
        if self._tenant_token and self._tenant_token_expires_at and self._tenant_token_expires_at > now:
            return self._tenant_token
        async with httpx.AsyncClient(base_url=settings.feishu_api_base, timeout=10.0) as client:
            resp = await client.post(
                settings.feishu_tenant_token_path,
                json={"app_id": settings.feishu_app_id, "app_secret": settings.feishu_app_secret},
            )
        try:
            resp.raise_for_status()
            payload = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Feishu tenant token request failed") from exc
        code = payload.get("code", 0)
        if code not in (0, None):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=payload.get("msg") or "Feishu token rejected")
        token = payload.get("tenant_access_token") or payload.get("data", {}).get("tenant_access_token")
        if not token:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Feishu tenant token missing")
        expire = int(payload.get("expire") or payload.get("data", {}).get("expire") or 7200)
        self.__class__._tenant_token = token
        self.__class__._tenant_token_expires_at = now + timedelta(seconds=max(expire - 300, 60))
        return token

    def _checked_feishu_response(self, response: httpx.Response) -> dict[str, Any]:
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Feishu contact request failed") from exc
        code = payload.get("code", 0)
        if code not in (0, None):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=payload.get("msg") or "Feishu contact rejected")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Feishu contact response missing data")
        return data

    def _upsert_departments(self, departments: list[FeishuDepartment]) -> dict[str, Department]:
        now = utcnow()
        # 不过滤 deleted_at：feishu_department_id 是 unique 索引（不区分软删），
        # 若只查未软删行会漏看软删记录，重新 INSERT 会撞 UNIQUE 约束。命中软删行则复活。
        existing = {
            row.feishu_department_id: row
            for row in self.db.scalars(
                select(Department).where(Department.feishu_department_id.is_not(None))
            ).all()
        }
        for item in departments:
            dept = existing.get(item.feishu_department_id)
            if dept is None:
                dept = Department(
                    name=item.name,
                    feishu_department_id=item.feishu_department_id,
                    sort_order=0,
                    last_synced_at=now,
                    created_by=self.actor.id,
                    updated_by=self.actor.id,
                )
                self.db.add(dept)
                self.db.flush()
                existing[item.feishu_department_id] = dept
            else:
                dept.name = item.name
                dept.deleted_at = None  # 复活被软删的部门
                dept.last_synced_at = now
                dept.updated_by = self.actor.id
        for item in departments:
            dept = existing.get(item.feishu_department_id)
            parent = existing.get(item.parent_feishu_department_id or "")
            if dept:
                dept.parent_id = parent.id if parent and dept.id != parent.id else None
        self.db.flush()
        return existing

    def _pick_primary_department(
        self, feishu_department_ids: list[str], dept_map: dict[str, Department]
    ) -> Department | None:
        """一个人属于多个部门时择优：最外层(depth 最小)优先；
        同层按 DEPARTMENT_PRIORITY 名称顺序；均未列举则按发现顺序(feishu_department_ids 的顺序)。
        """
        # 候选：保留传入顺序（= 飞书发现顺序），去掉不在 dept_map 的
        candidates = [dept_map[fid] for fid in feishu_department_ids if fid in dept_map]
        if not candidates:
            return None

        by_db_id = {d.id: d for d in dept_map.values()}

        def depth(dept: Department) -> int:
            d, steps = dept, 0
            seen: set[int] = set()
            while d.parent_id is not None and d.id not in seen and steps < 50:
                seen.add(d.id)
                parent = by_db_id.get(d.parent_id)
                if parent is None:
                    break
                d, steps = parent, steps + 1
            return steps

        priority = settings.department_priority_list

        def priority_rank(dept: Department) -> int:
            return priority.index(dept.name) if dept.name in priority else len(priority)

        # 稳定排序：先 depth，再优先级名次；同名次保持发现顺序
        ordered = sorted(
            enumerate(candidates),
            key=lambda pair: (depth(pair[1]), priority_rank(pair[1]), pair[0]),
        )
        return ordered[0][1]

    def _upsert_users(self, users: list[FeishuContactUser], dept_map: dict[str, Department]) -> tuple[int, int, int]:
        now = utcnow()
        created = updated = skipped = 0
        existing = {
            row.feishu_union_id: row
            for row in self.db.scalars(select(User).where(User.deleted_at.is_(None))).all()
        }
        for item in users:
            if not item.union_id:
                skipped += 1
                continue
            dept = self._pick_primary_department(item.department_ids, dept_map)
            user = existing.get(item.union_id)
            if user is None:
                role = "owner" if self._is_owner_union(item.union_id) else "member"
                user = User(
                    name=item.name,
                    email=item.email,
                    avatar_url=item.avatar_url,
                    role=role,
                    feishu_union_id=item.union_id,
                    feishu_open_id=item.open_id,
                    feishu_user_id=item.user_id,
                    feishu_message_receive_id=item.message_receive_id,
                    feishu_message_receive_id_type=item.message_receive_id_type,
                    department_id=dept.id if dept else None,
                    status="active",
                    sync_source="feishu",
                    last_synced_at=now,
                    created_by=self.actor.id,
                    updated_by=self.actor.id,
                )
                self.db.add(user)
                self.db.flush()
                self._grant_default_permissions(user)
                created += 1
            else:
                user.name = item.name
                user.email = item.email
                if not (user.avatar_url or "").startswith("/uploads/avatars/"):
                    user.avatar_url = item.avatar_url
                user.feishu_open_id = item.open_id
                user.feishu_user_id = item.user_id
                user.feishu_message_receive_id = item.message_receive_id
                user.feishu_message_receive_id_type = item.message_receive_id_type
                user.department_id = dept.id if dept else None
                user.sync_source = "feishu"
                user.last_synced_at = now
                user.disabled_reason = None
                if user.status != "active":
                    user.status = "active"
                if self._is_owner_union(item.union_id):
                    user.role = "owner"
                user.updated_by = self.actor.id
                updated += 1
        self.db.flush()
        return created, updated, skipped

    def _disable_missing_users(self, synced_union_ids: set[str]) -> int:
        disabled = 0
        for user in self.db.scalars(
            select(User).where(
                User.sync_source == "feishu",
                User.status == "active",
                User.deleted_at.is_(None),
            )
        ).all():
            if user.feishu_union_id in synced_union_ids:
                continue
            if self._is_owner_union(user.feishu_union_id) or user.role == "owner":
                continue
            user.status = "disabled"
            user.disabled_reason = "not_found_in_feishu_contact_sync"
            user.token_version += 1
            revoke_user_refresh_tokens(self.db, user.id, self.actor.id)
            user.updated_by = self.actor.id
            disabled += 1
        self.db.flush()
        return disabled

    def _grant_default_permissions(self, user: User) -> None:
        # Feature permissions apply by row for everyone (owner included, so they
        # can toggle their own). Owner still bypasses admin:* via role.
        wanted = list(dict.fromkeys(DEFAULT_FEATURE_PERMISSIONS + settings.default_permissions))
        for permission in wanted:
            self.db.add(
                UserPermission(
                    user_id=user.id,
                    permission=permission,
                    enabled=True,
                    created_by=self.actor.id,
                    updated_by=self.actor.id,
                )
            )

    def _finish_log(self, log_id: int, result: ContactSyncResult) -> None:
        log = self.db.get(ContactSyncLog, log_id)
        if log is None:
            return
        log.finished_at = result.finished_at
        log.status = result.status
        log.created_count = result.created
        log.updated_count = result.updated
        log.disabled_count = result.disabled
        log.skipped_count = result.skipped
        log.error_message = result.error_message
        log.updated_by = self.actor.id
        self.db.commit()

    def _is_owner_union(self, union_id: str) -> bool:
        return bool(settings.owner_feishu_union_id and union_id == settings.owner_feishu_union_id)

    def _string_field(self, item: dict[str, Any], *keys: str) -> str | None:
        for key in keys:
            value = item.get(key)
            if value is not None and value != "":
                return str(value)
        return None

    def _name_field(self, value: Any) -> str | None:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("name", "zh_cn", "en_us", "default"):
                if value.get(key):
                    return str(value[key])
        return None
