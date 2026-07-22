from __future__ import annotations

from datetime import date, time, timedelta
from decimal import Decimal
from io import BytesIO
import asyncio

from fastapi import HTTPException, Request, Response
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select

from app.core.security import hash_token, new_refresh_token, utcnow
from app.core.config import settings
from app.api.v1.auth import refresh_session
from app.main import app
from app.models.daily import DailyTaskCollaborator
from app.models.org import ContactSyncLog, Department
from app.models.traffic import TrafficMetricMember
from app.models.user import RefreshToken, User
from app.schemas.admin import DepartmentCreate, DepartmentUpdate, EmployeeUpdate
from app.schemas.daily import DailyTaskCreate, DailyTaskUpdate
from app.schemas.traffic import TrafficMetricCreate, TrafficMetricUpdate
from app.services.admin_service import AdminService
from app.services.daily_service import DailyService
from app.services.feishu_contact_service import FeishuContactService, FeishuDepartment
from app.services.traffic_service import TrafficService
from app.utils.image_upload import validate_raster_image


def _user(db, suffix: str, role: str = "member") -> User:
    row = User(
        name=f"User {suffix}",
        role=role,
        feishu_union_id=f"union-{suffix}",
        feishu_open_id=f"open-{suffix}",
        status="active",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def test_daily_collaborator_can_be_removed_and_readded(db):
    owner = _user(db, "daily-owner")
    collaborator = _user(db, "daily-collaborator")
    service = DailyService(db, owner)
    task = service.create_task(
        DailyTaskCreate(
            date=date(2026, 7, 10),
            task_time=time(9, 0),
            content="test",
            collaborator_ids=[collaborator.id],
        )
    )

    service.update_task(task.id, DailyTaskUpdate(collaborator_ids=[]))
    service.update_task(task.id, DailyTaskUpdate(collaborator_ids=[collaborator.id]))

    rows = db.scalars(
        select(DailyTaskCollaborator).where(DailyTaskCollaborator.task_id == task.id)
    ).all()
    assert len(rows) == 1
    assert rows[0].deleted_at is None


def test_traffic_member_can_be_removed_and_readded(db):
    owner = _user(db, "traffic-owner")
    viewer = _user(db, "traffic-viewer")
    service = TrafficService(db, owner)
    metric = service.create_metric(
        TrafficMetricCreate(
            name="weekly",
            direction="increase",
            weekly_target=Decimal("1"),
            viewer_ids=[viewer.id],
        )
    )

    service.update_metric(metric["id"], TrafficMetricUpdate(viewer_ids=[]))
    service.update_metric(metric["id"], TrafficMetricUpdate(viewer_ids=[viewer.id]))

    rows = db.scalars(
        select(TrafficMetricMember).where(TrafficMetricMember.metric_id == metric["id"])
    ).all()
    assert len(rows) == 1
    assert rows[0].deleted_at is None
    assert rows[0].role == "viewer"


def test_traffic_owner_must_be_explicitly_assigned_to_fill(db):
    owner = _user(db, "traffic-owner-assignment")
    service = TrafficService(db, owner)
    metric = service.create_metric(
        TrafficMetricCreate(
            name="weekly",
            direction="increase",
            weekly_target=Decimal("1"),
        )
    )

    assert metric["members"] == []
    assert metric["can_edit_values"] is False
    assert metric["is_pending"] is False
    try:
        service._get_metric(metric["id"], require_value_editor=True)
    except HTTPException as exc:
        assert exc.status_code == 403
    else:
        raise AssertionError("an unassigned owner must not be allowed to fill values")

    updated = service.update_metric(
        metric["id"], TrafficMetricUpdate(editor_ids=[owner.id])
    )

    assert updated["members"] == [
        {
            "user_id": owner.id,
            "name": owner.name,
            "avatar_url": owner.avatar_url,
            "role": "editor",
        }
    ]
    assert updated["can_edit_values"] is True
    assert updated["is_pending"] is True
    assert service._get_metric(metric["id"], require_value_editor=True).id == metric["id"]


def test_patch_can_clear_nullable_relationships(db):
    owner = _user(db, "admin", role="owner")
    employee = _user(db, "employee")
    service = AdminService(db, owner)
    department = service.create_department(DepartmentCreate(name="Parent"))
    child = service.create_department(
        DepartmentCreate(name="Child", parent_id=department.id)
    )
    employee.department_id = department.id
    db.commit()

    service.update_employee(employee.id, EmployeeUpdate(department_id=None, email=None))
    service.update_department(child.id, DepartmentUpdate(parent_id=None))

    db.refresh(employee)
    db.refresh(child)
    assert employee.department_id is None
    assert employee.email is None
    assert child.parent_id is None


def test_disabling_user_revokes_refresh_tokens(db):
    owner = _user(db, "session-admin", role="owner")
    employee = _user(db, "session-employee")
    token = RefreshToken(
        user_id=employee.id,
        token_hash=hash_token(new_refresh_token()),
        expires_at=utcnow() + timedelta(days=14),
    )
    db.add(token)
    db.commit()

    AdminService(db, owner).set_status(employee.id, "disabled")

    db.refresh(token)
    assert token.revoked_at is not None


def test_refresh_rotates_token_and_extends_session(db, monkeypatch):
    monkeypatch.setattr(settings, "jwt_secret", "test-secret-with-at-least-32-characters")
    employee = _user(db, "refresh-employee")
    raw_token = new_refresh_token()
    original = RefreshToken(
        user_id=employee.id,
        token_hash=hash_token(raw_token),
        expires_at=utcnow() + timedelta(days=1),
    )
    db.add(original)
    db.commit()

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/auth/refresh",
            "headers": [(b"user-agent", b"rotation-test")],
        }
    )
    response = Response()
    result = refresh_session(response, request, raw_token, db)

    assert result.user.id == employee.id
    db.refresh(original)
    assert original.revoked_at is not None
    rows = db.scalars(select(RefreshToken).where(RefreshToken.user_id == employee.id)).all()
    assert len(rows) == 2
    replacement = next(row for row in rows if row.id != original.id)
    assert replacement.token_hash != original.token_hash
    assert replacement.expires_at > original.expires_at


def test_oauth_state_is_bound_to_browser_cookie():
    client = TestClient(app)
    login = client.get("/api/v1/auth/feishu/login-config")
    assert login.status_code == 200
    assert client.cookies.get("oauth_state") == login.json()["state"]

    callback = client.post(
        "/api/v1/auth/feishu/callback",
        json={"code": "unused", "state": "wrong-state"},
    )
    assert callback.status_code == 400


def test_raster_validation_checks_content_mime_and_extension():
    buffer = BytesIO()
    Image.new("RGB", (32, 32), "blue").save(buffer, format="PNG")
    content = buffer.getvalue()

    assert validate_raster_image(
        content,
        filename="avatar.png",
        content_type="image/png",
    ) == ".png"

    for filename, content_type in (("avatar.jpg", "image/png"), ("avatar.png", "image/jpeg")):
        try:
            validate_raster_image(content, filename=filename, content_type=content_type)
        except ValueError:
            pass
        else:
            raise AssertionError("mismatched image metadata must be rejected")


def test_contact_sync_rolls_back_partial_database_changes(db, monkeypatch):
    actor = _user(db, "sync-actor", role="owner")
    service = FeishuContactService(db, actor)

    async def _departments():
        return [FeishuDepartment(feishu_department_id="dept-1", name="Dept")]

    async def _users(_departments):
        return []

    def _fail_after_department_flush(_users, _dept_map):
        raise RuntimeError("simulated user upsert failure")

    monkeypatch.setattr(service, "_fetch_departments", _departments)
    monkeypatch.setattr(service, "_fetch_users", _users)
    monkeypatch.setattr(service, "_upsert_users", _fail_after_department_flush)

    try:
        asyncio.run(service.sync_contacts())
    except RuntimeError as exc:
        assert str(exc) == "simulated user upsert failure"
    else:
        raise AssertionError("sync should propagate the database phase failure")

    assert db.scalar(select(Department).where(Department.feishu_department_id == "dept-1")) is None
    log = db.scalar(select(ContactSyncLog).order_by(ContactSyncLog.id.desc()))
    assert log is not None
    assert log.status == "failed"
