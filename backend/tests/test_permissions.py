from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — register all tables on Base.metadata
from app.api.v1.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User, UserPermission


def _grant(session, user_id: int, permissions: list[str]) -> None:
    for p in permissions:
        session.add(UserPermission(user_id=user_id, permission=p, enabled=True))
    session.commit()


@pytest.fixture()
def env():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()

    def _get_db():
        yield session

    app.dependency_overrides[get_db] = _get_db
    c = TestClient(app)
    c.cookies.set("csrf_token", "t")
    c.headers.update({"X-CSRF-Token": "t"})
    try:
        yield session, c
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(engine)


def _member(session, permissions: list[str]) -> User:
    u = User(
        name="M", role="member", feishu_union_id="u-m", feishu_open_id="o-m", status="active"
    )
    session.add(u)
    session.commit()
    session.refresh(u)
    _grant(session, u.id, permissions)
    return u


def test_daily_blocked_without_feature(env):
    session, c = env
    member = _member(session, permissions=["feature:okr"])  # no feature:daily
    app.dependency_overrides[get_current_user] = lambda: member
    r = c.get("/api/v1/daily?date=2026-07-10")
    assert r.status_code == 403
    assert c.get("/api/v1/subscriptions/daily").status_code == 403


def test_daily_allowed_with_feature(env):
    session, c = env
    member = _member(session, permissions=["feature:daily"])
    app.dependency_overrides[get_current_user] = lambda: member
    r = c.get("/api/v1/daily?date=2026-07-10")
    assert r.status_code == 200
    assert c.get("/api/v1/subscriptions/daily").status_code == 200


def test_okr_subscription_requires_okr_feature(env):
    session, c = env
    member = _member(session, permissions=["feature:daily"])
    app.dependency_overrides[get_current_user] = lambda: member
    assert c.get("/api/v1/subscriptions/okr").status_code == 403
    _grant(session, member.id, ["feature:okr"])
    assert c.get("/api/v1/subscriptions/okr").status_code == 200


def test_profile_subscription_only_enables_authorized_features(env):
    session, c = env
    member = _member(session, permissions=["feature:daily"])
    target = User(
        name="Target",
        role="member",
        feishu_union_id="u-target",
        feishu_open_id="o-target",
        status="active",
    )
    session.add(target)
    session.commit()
    session.refresh(target)
    app.dependency_overrides[get_current_user] = lambda: member

    response = c.post(f"/api/v1/people/{target.id}/subscribe")
    assert response.status_code == 200
    assert response.json()["daily_enabled"] is True
    assert response.json()["okr_enabled"] is False


def test_owner_feature_gate_is_by_row(env):
    # Feature perms apply by row even for owner — no row means blocked, so owner
    # can toggle their own module visibility.
    session, c = env
    owner = User(
        name="O", role="owner", feishu_union_id="u-o", feishu_open_id="o-o", status="active"
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)
    app.dependency_overrides[get_current_user] = lambda: owner

    assert c.get("/api/v1/daily?date=2026-07-10").status_code == 403
    _grant(session, owner.id, ["feature:daily"])
    assert c.get("/api/v1/daily?date=2026-07-10").status_code == 200


def test_owner_bypasses_admin_gate_without_row(env):
    # Owner keeps admin:* access by role so they can't lock themselves out.
    session, c = env
    owner = User(
        name="O2", role="owner", feishu_union_id="u-o2", feishu_open_id="o-o2", status="active"
    )
    session.add(owner)
    session.commit()
    app.dependency_overrides[get_current_user] = lambda: owner
    # /groups is feature-gated (not admin) → blocked without row.
    assert c.get("/api/v1/groups").status_code == 403
    # employee admin list is admin:employee → owner passes by role.
    assert c.get("/api/v1/admin/employees").status_code == 200
    assert c.get("/api/v1/admin/feishu/sync-logs").status_code == 200


def test_groups_require_feature_group(env):
    session, c = env
    member = _member(session, permissions=["feature:daily"])  # no feature:group
    app.dependency_overrides[get_current_user] = lambda: member
    assert c.get("/api/v1/groups").status_code == 403


def test_groups_crud_with_feature_group(env):
    session, c = env
    member = _member(session, permissions=["feature:group"])
    app.dependency_overrides[get_current_user] = lambda: member

    assert c.get("/api/v1/groups").json() == []
    created = c.post("/api/v1/groups", json={"name": "核心组"})
    assert created.status_code == 200
    gid = created.json()["id"]

    assert c.patch(f"/api/v1/groups/{gid}", json={"name": "核心团队"}).json()["name"] == "核心团队"
    assert c.get("/api/v1/groups/import-sources").status_code == 200
    assert c.delete(f"/api/v1/groups/{gid}").status_code == 204


def test_okr_progress_history_and_comments(env):
    session, c = env
    owner = User(
        name="OKR Owner",
        role="owner",
        feishu_union_id="u-okr-owner",
        feishu_open_id="o-okr-owner",
        status="active",
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)
    _grant(session, owner.id, ["feature:okr"])
    app.dependency_overrides[get_current_user] = lambda: owner

    created = c.post(
        "/api/v1/okr/objectives",
        json={
            "month": "2026-07",
            "title": "交付核心项目",
            "key_results": [
                {"title": "完成验收"}
            ],
        },
    )
    assert created.status_code == 200
    objective = created.json()
    objective_id = objective["id"]
    kr_id = objective["key_results"][0]["id"]

    progress = c.post(
        f"/api/v1/okr/key-results/{kr_id}/progress",
        json={
            "note": "已完成第一轮验收",
            "progress_date": "2026-07-15",
        },
    )
    assert progress.status_code == 200
    assert progress.json()["note"] == "已完成第一轮验收"
    assert "current_value" not in progress.json()
    assert "progress" not in progress.json()

    month = c.get("/api/v1/okr?month=2026-07").json()
    updated_kr = month["objectives"][0]["key_results"][0]
    assert updated_kr["progress"] == "0.00"
    assert updated_kr["progress_updates"][0]["progress_date"] == "2026-07-15"
    assert month["objectives"][0]["progress"] == "0.00"

    marked_kr = c.patch(f"/api/v1/okr/key-results/{kr_id}", json={"progress": 35})
    assert marked_kr.status_code == 200
    marked_kr_payload = marked_kr.json()["key_results"][0]
    assert marked_kr_payload["progress"] == "35.00"
    assert marked_kr.json()["progress"] == "35.00"

    edited_kr = c.patch(f"/api/v1/okr/key-results/{kr_id}", json={"title": "验收描述已更新"})
    assert edited_kr.status_code == 200
    edited_kr_payload = edited_kr.json()["key_results"][0]
    assert edited_kr_payload["title"] == "验收描述已更新"
    assert edited_kr_payload["progress"] == "35.00"

    rejected_current_value = c.patch(
        f"/api/v1/okr/key-results/{kr_id}",
        json={"current_value": 9},
    )
    assert rejected_current_value.status_code == 422

    outside_month = c.post(
        f"/api/v1/okr/key-results/{kr_id}/progress",
        json={"note": "错误月份", "progress_date": "2026-08-01"},
    )
    assert outside_month.status_code == 422

    objective_comment = c.post(
        f"/api/v1/okr/objectives/{objective_id}/comments",
        json={"content": "目标范围已确认"},
    )
    assert objective_comment.status_code == 200
    assert objective_comment.json()["author"]["name"] == "OKR Owner"

    kr_comment = c.post(
        f"/api/v1/okr/key-results/{kr_id}/comments",
        json={"content": "验收材料需要补齐"},
    )
    assert kr_comment.status_code == 200
    comment_id = kr_comment.json()["id"]
    edited = c.patch(
        f"/api/v1/okr/comments/{comment_id}",
        json={"content": "验收材料已经补齐"},
    )
    assert edited.status_code == 200
    assert edited.json()["content"] == "验收材料已经补齐"
    assert len(c.get(f"/api/v1/okr/key-results/{kr_id}/comments").json()) == 1
    assert c.delete(f"/api/v1/okr/comments/{comment_id}").status_code == 204
    assert c.get(f"/api/v1/okr/key-results/{kr_id}/comments").json() == []

    refreshed = c.get("/api/v1/okr?month=2026-07").json()
    assert refreshed["objectives"][0]["comment_count"] == 1
    assert refreshed["objectives"][0]["key_results"][0]["comment_count"] == 0
