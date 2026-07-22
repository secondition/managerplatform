from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — register all tables on Base.metadata
from sqlalchemy.pool import StaticPool

from app.api.v1.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.user import User
from app.services.ai.provider import AiProviderNotConfigured, AiResponse


@pytest.fixture()
def client(monkeypatch):
    # StaticPool + a single shared connection so the TestClient worker thread
    # sees the same in-memory DB that create_all populated.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()

    owner = User(
        name="Owner", role="owner", feishu_union_id="u-o", feishu_open_id="o-o", status="active"
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)
    # Feature perms apply by row for everyone (owner included); AI daily/okr
    # endpoints live under the feature-gated daily/okr routers.
    from app.models.user import UserPermission

    for perm in ("feature:daily", "feature:okr"):
        session.add(UserPermission(user_id=owner.id, permission=perm, enabled=True))
    session.commit()

    def _get_db():
        yield session

    app.dependency_overrides[get_db] = _get_db
    app.dependency_overrides[get_current_user] = lambda: owner

    # A mock provider that echoes a fixed JSON payload for whatever prompt.
    class _MockProvider:
        async def chat(self, model, messages, **kwargs):
            if any("今日行动建议官" in message["content"] for message in messages):
                payload = {
                    "summary": "今天先推动最临期事项。",
                    "suggestions": [
                        {
                            "type": "amber",
                            "title": "补齐供应商报价",
                            "reason": "月底临近且可独立推进。",
                            "linked": {"my_kr": "KR4", "others": ""},
                            "needs_info": False,
                            "ask": {"question": "", "options": []},
                        }
                    ],
                }
            elif any("月报评分引擎" in message["content"] for message in messages):
                payload = {
                    "total_score": 78,
                    "summary": "汇报认真，复盘深度较好。",
                    "dimension_scores": {
                        "复盘与思考深度": {"score": 40, "full": 50, "note": "因果清楚"},
                        "工作饱和度": {"score": 16, "full": 20, "note": "更新正常"},
                        "真实性与一致性": {"score": 12, "full": 15, "note": "基本一致"},
                        "业绩与目标达成": {"score": 10, "full": 15, "note": "结果明确"},
                    },
                    "doubts": ["一项成果缺少日报过程"],
                    "suggestions": ["补充决策过程", "沉淀复用方法"],
                }
            elif any("OKR 质量评分引擎" in message["content"] for message in messages):
                payload = {
                    "total_score": 85,
                    "level": "扎实优秀",
                    "summary": "方向和支撑都比较扎实。",
                    "dimension_scores": {
                        "O的价值": {"score": 36, "full": 40, "note": "方向对准业务"},
                        "KR支撑度": {"score": 26, "full": 30, "note": "支撑完整"},
                        "工作饱和度": {"score": 23, "full": 30, "note": "事务量正常"},
                    },
                    "highlights": ["方向清晰"],
                    "optional_improvements": [
                        {
                            "target": "KR1",
                            "point": "可以更具体",
                            "suggestion": "补充目标值",
                        }
                    ],
                    "impact_on_daily_scoring": "写得越具体，日报评分越准确。",
                }
            elif "周工作表现评分引擎" in messages[0]["content"]:
                payload = {
                    "total_score": 72,
                    "level": "达标踏实",
                    "summary": "本周整体推进稳定。",
                    "dimension_scores": {
                        "产出与结果": {"score": 28, "full": 40, "note": "有阶段结果"},
                        "问题方案质量": {"score": 22, "full": 30, "note": "逻辑清楚"},
                        "工作饱和度": {"score": 22, "full": 30, "note": "负荷正常"},
                    },
                    "key_achievements": ["完成阶段方案"],
                    "concerns": ["需加强闭环"],
                    "manager_hint": "保持跟进",
                }
            else:
                payload = {
                    "total_score": 80,
                    "level": "达标",
                    "trend_note": "稳定",
                    "one_line_review": "不错",
                    "dimensions": [
                        {"name": "重要性", "score": 32, "full": 40},
                        {"name": "质量", "score": 26, "full": 30},
                        {"name": "饱和度", "score": 22, "full": 30},
                    ],
                    "okr_outside_high_value": [],
                    "manager_hint": "",
                    "okr_clarity_warning": "",
                }
            return AiResponse(content=json.dumps(payload), model=model)

    monkeypatch.setattr(
        "app.services.ai_service.build_provider", lambda db: (_MockProvider(), "mock")
    )

    # CSRF double-submit: set matching cookie + header on the client.
    c = TestClient(app)
    c.cookies.set("csrf_token", "t")
    c.headers.update({"X-CSRF-Token": "t"})
    try:
        yield c
    finally:
        app.dependency_overrides.clear()
        session.close()
        Base.metadata.drop_all(engine)


def test_admin_provider_key_masked(client):
    r = client.patch(
        "/api/v1/admin/ai/provider",
        json={"provider": "deepseek", "default_model": "deepseek-chat", "api_key": "TEST_NOT_A_SECRET", "enabled": True},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["api_key_set"] is True
    assert "TEST_NOT_A_SECRET" not in json.dumps(body)  # never leaks raw key
    assert body["api_key_masked"].startswith("TES")

    # GET keeps it masked
    got = client.get("/api/v1/admin/ai/provider").json()
    assert got["api_key_set"] is True
    assert got["default_model"] == "deepseek-chat"


def test_daily_score_flow(client):
    # empty first
    empty = client.get("/api/v1/daily/scores?date=2026-07-10").json()
    assert empty["status"] == "empty"

    gen = client.post("/api/v1/daily/scores/generate?date=2026-07-10")
    assert gen.status_code == 200, gen.text
    body = gen.json()
    assert body["status"] == "ready"
    assert body["total_score"] == 80
    assert len(body["dimensions"]) == 3

    # persisted
    again = client.get("/api/v1/daily/scores?date=2026-07-10").json()
    assert again["status"] == "ready" and again["total_score"] == 80


def test_weekly_score_flow(client):
    empty = client.get("/api/v1/daily/weekly-score?date=2026-07-10").json()
    assert empty["status"] == "empty"

    generated = client.post("/api/v1/daily/weekly-score/generate?date=2026-07-10")
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["status"] == "ready"
    assert body["week_start"] == "2026-06-29"
    assert body["week_end"] == "2026-07-05"
    assert body["total_score"] == 72
    assert len(body["dimensions"]) == 3

    again = client.get("/api/v1/daily/weekly-score?date=2026-07-10").json()
    assert again["status"] == "ready" and again["total_score"] == 72


def test_daily_suggestion_accepts_realtime_supplement(client):
    generated = client.post(
        "/api/v1/daily/suggestions/generate?date=2026-07-10",
        json={"realtime_supplement": "供应商今天可以给最终报价"},
    )
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["status"] == "ready"
    assert body["summary"] == "今天先推动最临期事项。"
    assert body["items"][0]["suggestion_type"] == "amber"
    assert body["items"][0]["linked"]["my_kr"] == "KR4"


def test_okr_quality_review_flow(client):
    empty = client.get("/api/v1/okr/review?month=2026-07").json()
    assert empty["status"] == "empty"

    generated = client.post("/api/v1/okr/review/generate?month=2026-07")
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["status"] == "ready"
    assert float(body["total_score"]) == 85
    assert body["level"] == "扎实优秀"
    assert len(body["dimensions"]) == 3
    assert body["highlights"] == ["方向清晰"]
    assert body["optional_improvements"][0]["target"] == "KR1"


def test_monthly_report_score_flow(client):
    empty = client.get("/api/v1/okr/monthly-report/score?month=2026-07").json()
    assert empty["status"] == "empty"

    generated = client.post("/api/v1/okr/monthly-report/score/generate?month=2026-07")
    assert generated.status_code == 200, generated.text
    body = generated.json()
    assert body["status"] == "ready"
    assert body["total_score"] == 78
    assert len(body["dimensions"]) == 4
    assert body["doubts"] == ["一项成果缺少日报过程"]
    assert len(body["suggestions"]) == 2


def test_unconfigured_provider_returns_not_enabled_state(client, monkeypatch):
    def _not_configured(_db):
        raise AiProviderNotConfigured("AI provider is not enabled")

    monkeypatch.setattr("app.services.ai_service.build_provider", _not_configured)
    response = client.post("/api/v1/daily/scores/generate?date=2026-07-12")
    assert response.status_code == 200
    assert response.json()["status"] == "not_enabled"


def test_user_facing_features_reflects_admin_toggle(client):
    # Default: all on. User-facing read is open to any authenticated user.
    flags = client.get("/api/v1/ai/features").json()
    assert flags["daily_score_enabled"] is True

    # Admin turns daily score off; user-facing read + generate both reflect it.
    client.patch("/api/v1/admin/ai/features", json={"daily_score_enabled": False})
    assert client.get("/api/v1/ai/features").json()["daily_score_enabled"] is False
    gen = client.post("/api/v1/daily/scores/generate?date=2026-07-11")
    assert gen.json()["status"] == "not_enabled"


def test_prompts_list_and_restore(client):
    lst = client.get("/api/v1/admin/ai/prompts").json()
    types = {p["prompt_type"] for p in lst}
    assert types == {
        "daily_score",
        "weekly_score",
        "daily_suggestion",
        "okr_quality",
        "monthly_report_score",
    }

    weekly = next(p for p in lst if p["prompt_type"] == "weekly_score")
    assert {v["key"] for v in weekly["available_variables"]} == {
        "weekly_reports",
        "weekly_problems",
        "okr_content",
    }

    daily = next(p for p in lst if p["prompt_type"] == "daily_score")
    # Variables are a selectable catalog now — no {placeholder} tokens in the body.
    assert "{checklist}" not in daily["template_content"]
    assert {v["key"] for v in daily["available_variables"]} >= {"checklist", "problems"}
    assert "checklist" in daily["variables"]

    r = client.post("/api/v1/admin/ai/prompts/daily_score/restore-default")
    assert r.status_code == 200
    body = r.json()
    assert set(body["variables"]) == {
        "date",
        "checklist",
        "problems",
        "okr_content",
        "user_notes",
        "memory",
    }


def test_prompt_update_variables_and_version(client):
    # Deselect a variable + set a custom version string.
    r = client.patch(
        "/api/v1/admin/ai/prompts/daily_score",
        json={"variables": ["checklist", "problems"], "version": "v2.0"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["variables"] == ["checklist", "problems"]
    assert body["version"] == "v2.0"

    # Unknown keys are filtered against the catalog.
    r = client.patch(
        "/api/v1/admin/ai/prompts/daily_score",
        json={"variables": ["checklist", "bogus"]},
    )
    assert r.json()["variables"] == ["checklist"]
