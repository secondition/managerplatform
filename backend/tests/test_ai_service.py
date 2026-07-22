from __future__ import annotations

import json
from datetime import date, time

import pytest
from sqlalchemy import func, select

from app.models.ai import AiTask, MonthlyReportScore, WeeklyScore
from app.models.daily import DailyReport, DailyTask, ProblemSolution
from app.models.okr import MonthlyReportSection
from app.schemas.ai_provider import validate_provider_output
from app.services.ai.provider import AiProviderError, AiResponse
from app.services.ai_service import AiService


class _MockProvider:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    async def chat(self, model, messages, **kwargs) -> AiResponse:
        return AiResponse(content=json.dumps(self._payload), model=model)


class _SequenceProvider:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.calls: list[dict] = []

    async def chat(self, model, messages, **kwargs) -> AiResponse:
        self.calls.append({"messages": messages, "kwargs": kwargs})
        return AiResponse(content=self.contents.pop(0), model=model)


@pytest.fixture()
def patch_provider(monkeypatch):
    def _patch(payload: dict, model: str = "mock-model"):
        monkeypatch.setattr(
            "app.services.ai_service.build_provider",
            lambda db: (_MockProvider(payload), model),
        )

    return _patch


def test_generate_daily_score(db, user, daily_report, patch_provider):
    patch_provider(
        {
            "total_score": 82,
            "level": "达标",
            "trend_note": "较昨日提升",
            "one_line_review": "推进有力",
            "dimensions": [
                {"name": "重要性", "score": 34, "full": 40},
                {"name": "质量", "score": 26, "full": 30},
                {"name": "饱和度", "score": 22, "full": 30},
            ],
            "okr_outside_high_value": ["协助同事"],
            "manager_hint": "关注质量",
            "okr_clarity_warning": "",
        }
    )
    row = AiService(db, user).generate_daily_score(date(2026, 7, 10))
    assert row.total_score == 82
    assert row.level == "达标"
    assert len(row.dimensions_json) == 3

    # Persisted + re-readable.
    got = AiService(db, user).get_daily_score(date(2026, 7, 10))
    assert got is not None and got.total_score == 82


def test_daily_score_new_shape_and_memory_writeback(db, user, daily_report, patch_provider):
    # New template output: dimensions object, okr_outside object, memory_update.
    patch_provider(
        {
            "total_score": 88,
            "level": "达标踏实",
            "trend_note": "较昨日 +4",
            "one_line_review": "问题剖析到位",
            "dimensions": {
                "importance_quality": {"label": "事项的重要性与产出", "score": 34, "max": 40, "note": "推动 KR2"},
                "problem_solution_quality": {"label": "工作质量", "score": 24, "max": 30, "note": "根因定位"},
                "work_saturation": {"label": "当日工作饱和度", "score": 30, "max": 30, "note": "约8.5小时"},
            },
            "okr_outside_high_value": {
                "ratio": "约40%",
                "items": ["紧急止损"],
                "manager_hint": "考虑提为新KR",
            },
            "memory_update": {
                "recurring_strengths_delta": ["问题定位深入"],
                "recurring_issues_delta": ["清单偏流水账"],
                "resolved_issues": [],
                "profile_note": "执行力强、擅长根因分析",
            },
            "okr_clarity_warning": "",
        }
    )
    service = AiService(db, user)
    row = service.generate_daily_score(date(2026, 7, 10))
    assert row.total_score == 88
    # dimensions object normalized to a 3-item list in fixed order.
    assert [d["name"] for d in row.dimensions_json] == [
        "事项的重要性与产出",
        "工作质量",
        "当日工作饱和度",
    ]
    # manager_hint lifted out of the okr_outside object.
    assert row.manager_hint == "考虑提为新KR"

    # memory_update folded into AiUserMemory.
    mem = service._get_user_memory(user.id)
    assert "问题定位深入" in mem.recurring_strengths_json
    assert "清单偏流水账" in mem.recurring_issues_json
    assert mem.last_summary == "执行力强、擅长根因分析"

    # Serialized output exposes ratio + items.
    from app.services.ai_serialize import serialize_daily_score

    out = serialize_daily_score(row)
    assert out.okr_outside_ratio == "约40%"
    assert out.okr_outside_high_value == ["紧急止损"]


def test_generate_suggestions_and_accept(db, user, daily_report, patch_provider):
    patch_provider(
        {
            "summary": "今天先处理事项A。",
            "suggestions": [
                {
                    "type": "red",
                    "title": "跟进A渠道",
                    "reason": "转化下滑",
                    "linked": {"my_kr": "KR1", "others": "A渠道日报"},
                    "needs_info": False,
                    "ask": {"question": "", "options": []},
                },
                {
                    "type": "amber",
                    "title": "复盘B",
                    "reason": "沉淀",
                    "linked": {"my_kr": "", "others": ""},
                    "needs_info": False,
                    "ask": {"question": "", "options": []},
                },
            ],
        }
    )
    service = AiService(db, user)
    items = service.generate_suggestions(date(2026, 7, 10))
    assert len(items) == 2
    assert items[0].suggestion_type == "red"
    assert items[0].linked_json["my_kr"] == "KR1"
    assert service.latest_suggestion_summary(date(2026, 7, 10)) == "今天先处理事项A。"

    accepted = service.accept_suggestion(items[0])
    assert accepted.status == "accepted"
    assert accepted.accepted_task_id is not None
    accepted_again = service.accept_suggestion(items[0])
    assert accepted_again.accepted_task_id == accepted.accepted_task_id
    task_count = db.scalar(
        select(func.count(DailyTask.id)).where(DailyTask.source == "suggestion")
    )
    assert task_count == 1
    remaining_after_accept = service.list_suggestions(date(2026, 7, 10))
    assert all(s.status == "pending" for s in remaining_after_accept)
    assert items[0].id not in {s.id for s in remaining_after_accept}

    # accepted and rejected suggestions both drop out of the visible list
    service.reject_suggestion(items[1])
    remaining = service.list_suggestions(date(2026, 7, 10))
    assert remaining == []


def test_suggestion_uses_system_role_layers_and_remembers_supplement(
    db, user, daily_report, objective, monkeypatch
):
    payload = {
        "summary": "优先补齐信息。",
        "suggestions": [
            {
                "type": "amber",
                "title": "确认部门A交付时间",
                "reason": "当前补充说明正在等待部门A。",
                "linked": {"my_kr": "提升指标A", "others": "部门A"},
                "needs_info": True,
                "ask": {
                    "question": "部门A预计何时交付？",
                    "options": ["今天", "本周", "尚未确认"],
                },
            }
        ],
    }
    provider = _SequenceProvider([json.dumps(payload), json.dumps(payload)])
    monkeypatch.setattr(
        "app.services.ai_service.build_provider", lambda db: (provider, "mock-model")
    )
    service = AiService(db, user)

    service.generate_suggestions(
        date(2026, 7, 10), realtime_supplement="这件事在等部门A交付"
    )
    service.generate_suggestions(date(2026, 7, 10), realtime_supplement="部门A尚未确认")

    assert provider.calls[0]["messages"][0]["role"] == "system"
    assert "今日行动建议官" in provider.calls[0]["messages"][0]["content"]
    assert provider.calls[0]["messages"][1]["role"] == "user"
    assert "【第一层·全公司相关文字】" in provider.calls[0]["messages"][1]["content"]
    assert "【第二层·我的 OKR】" in provider.calls[0]["messages"][1]["content"]
    assert "提升指标A" in provider.calls[0]["messages"][1]["content"]
    assert provider.calls[0]["kwargs"]["max_tokens"] == 3000
    latest_task = db.scalar(select(AiTask).order_by(AiTask.id.desc()))
    assert latest_task is not None
    assert "这件事在等部门A交付" in latest_task.input_json["my_manual_context"]


def test_generate_okr_review(db, user, objective, patch_provider):
    patch_provider(
        {
            "total_score": 82,
            "level": "扎实优秀",
            "summary": "方向清晰，KR 支撑较完整。",
            "dimension_scores": {
                "O的价值": {"score": 34, "full": 40, "note": "对准业务增长"},
                "KR支撑度": {"score": 24, "full": 30, "note": "关键环节较完整"},
                "工作饱和度": {"score": 24, "full": 30, "note": "事务量正常"},
            },
            "highlights": ["目标方向明确"],
            "optional_improvements": [
                {
                    "target": "提升指标A",
                    "point": "可以补充目标增量",
                    "suggestion": "增加本月目标区间",
                }
            ],
            "impact_on_daily_scoring": "KR 越具体，日报事项相关度判断越准确。",
        }
    )
    row = AiService(db, user).generate_okr_review("2026-07")
    assert int(row.quality_score) == 82
    assert row.level == "扎实优秀"
    assert len(row.dimensions_json) == 3
    assert row.highlights_json == ["目标方向明确"]
    assert row.optional_improvements_json[0]["target"] == "提升指标A"


def test_okr_quality_input_excludes_completion_data(
    db, user, objective, monkeypatch
):
    payload = {
        "total_score": 75,
        "level": "认真合格",
        "summary": "整体方向合理。",
        "dimension_scores": {
            "O的价值": {"score": 30, "full": 40, "note": "方向合理"},
            "KR支撑度": {"score": 23, "full": 30, "note": "支撑基本完整"},
            "工作饱和度": {"score": 22, "full": 30, "note": "事务量正常"},
        },
        "highlights": [],
        "optional_improvements": [],
        "impact_on_daily_scoring": "建议写具体，以提升日报相关度判断。",
    }
    provider = _SequenceProvider([json.dumps(payload)])
    monkeypatch.setattr(
        "app.services.ai_service.build_provider", lambda db: (provider, "mock-model")
    )

    AiService(db, user).generate_okr_review("2026-07")

    task = db.scalar(select(AiTask).order_by(AiTask.id.desc()))
    assert task is not None
    assert set(task.input_json) == {"month", "okr_content"}
    assert "提升指标A" in task.input_json["okr_content"]
    assert "当前" not in task.input_json["okr_content"]
    assert "进度" not in task.input_json["okr_content"]


def test_okr_quality_provider_requires_matching_dimension_total():
    with pytest.raises(ValueError, match="total_score"):
        validate_provider_output(
            "okr_quality",
            {
                "total_score": 80,
                "level": "扎实优秀",
                "summary": "整体不错",
                "dimension_scores": {
                    "O的价值": {"score": 34, "full": 40, "note": "方向明确"},
                    "KR支撑度": {"score": 24, "full": 30, "note": "支撑较好"},
                    "工作饱和度": {"score": 24, "full": 30, "note": "事务饱满"},
                },
                "impact_on_daily_scoring": "具体程度会影响日报评分。",
            },
        )


def test_generate_monthly_report_score_aggregates_month_data(
    db, user, daily_report, objective, patch_provider
):
    db.add_all(
        [
            ProblemSolution(
                report_id=daily_report.id,
                user_id=user.id,
                problem_text="流程阻塞",
                solution_html="<p>拆分步骤并复盘流程</p>",
            ),
            MonthlyReportSection(
                user_id=user.id,
                month="2026-07",
                section_key="performance",
                title="进展相关",
                content_html="<p>通过步骤拆分找到了阻塞原因</p>",
            ),
        ]
    )
    db.commit()
    patch_provider(
        {
            "total_score": 78,
            "summary": "复盘有因果，过程记录还可更完整。",
            "dimension_scores": {
                "复盘与思考深度": {"score": 40, "full": 50, "note": "问题方案具体"},
                "工作饱和度": {"score": 16, "full": 20, "note": "清单量正常"},
                "真实性与一致性": {"score": 12, "full": 15, "note": "主要成果可印证"},
                "业绩与目标达成": {"score": 10, "full": 15, "note": "有结果说明"},
            },
            "doubts": ["部分成果缺少过程记录"],
            "suggestions": ["补充关键决策过程", "沉淀可复用方法"],
        }
    )
    service = AiService(db, user)

    first = service.generate_monthly_report_score("2026-07")
    second = service.generate_monthly_report_score("2026-07")

    assert first.id == second.id
    assert first.total_score == 78
    assert len(first.dimensions_json) == 4
    assert db.scalar(select(func.count(MonthlyReportScore.id))) == 1
    task = db.scalar(
        select(AiTask)
        .where(AiTask.task_type == "monthly_report_score")
        .order_by(AiTask.id.desc())
    )
    assert task is not None
    assert set(task.input_json) == {
        "month_overview",
        "daily_digest",
        "okr_content",
        "monthly_report_content",
    }
    assert "工作清单：共 1 条" in task.input_json["month_overview"]
    assert "流程阻塞" in task.input_json["daily_digest"]
    assert "拆分步骤并复盘流程" in task.input_json["daily_digest"]
    assert "提升指标A" in task.input_json["okr_content"]
    assert "找到了阻塞原因" in task.input_json["monthly_report_content"]


def test_monthly_report_provider_requires_matching_dimension_total():
    with pytest.raises(ValueError, match="total_score"):
        validate_provider_output(
            "monthly_report_score",
            {
                "total_score": 77,
                "summary": "整体认真",
                "dimension_scores": {
                    "复盘与思考深度": {"score": 40, "full": 50, "note": "复盘较深"},
                    "工作饱和度": {"score": 16, "full": 20, "note": "事务正常"},
                    "真实性与一致性": {"score": 12, "full": 15, "note": "基本一致"},
                    "业绩与目标达成": {"score": 10, "full": 15, "note": "结果尚可"},
                },
                "suggestions": ["补充过程", "强化因果"],
            },
        )


def test_provider_error_records_failed_task(db, user, daily_report, monkeypatch):
    def _boom(db):
        raise AiProviderError("not enabled")

    monkeypatch.setattr("app.services.ai_service.build_provider", _boom)
    with pytest.raises(AiProviderError):
        AiService(db, user).generate_daily_score(date(2026, 7, 10))
    task = db.scalar(select(AiTask).order_by(AiTask.id.desc()))
    assert task is not None
    assert task.status == "failed"


def test_invalid_provider_shape_records_failed_task(db, user, daily_report, patch_provider):
    patch_provider([])
    with pytest.raises(AiProviderError):
        AiService(db, user).generate_daily_score(date(2026, 7, 10))
    task = db.scalar(select(AiTask).order_by(AiTask.id.desc()))
    assert task is not None
    assert task.status == "failed"


def test_truncated_daily_score_json_retries_once(db, user, daily_report, monkeypatch):
    valid = {
        "total_score": 80,
        "level": "达标",
        "dimensions": [
            {"name": "重要性", "score": 32, "full": 40},
            {"name": "质量", "score": 26, "full": 30},
            {"name": "饱和度", "score": 22, "full": 30},
        ],
    }
    provider = _SequenceProvider(['{"total_score": 80, "one_line_review": "未结束', json.dumps(valid)])
    monkeypatch.setattr(
        "app.services.ai_service.build_provider", lambda db: (provider, "mock-model")
    )

    row = AiService(db, user).generate_daily_score(date(2026, 7, 10))

    assert row.total_score == 80
    assert len(provider.calls) == 2
    assert all(call["kwargs"]["max_tokens"] == 4096 for call in provider.calls)
    assert "上一次输出不是完整且符合字段约束的合法 JSON" in provider.calls[1]["messages"][-1]["content"]
    task = db.scalar(select(AiTask).order_by(AiTask.id.desc()))
    assert task is not None and task.status == "succeeded"


def test_truncated_json_twice_records_failed_task(db, user, daily_report, monkeypatch):
    provider = _SequenceProvider(['{"total_score":', '{"total_score":'])
    monkeypatch.setattr(
        "app.services.ai_service.build_provider", lambda db: (provider, "mock-model")
    )

    with pytest.raises(AiProviderError):
        AiService(db, user).generate_daily_score(date(2026, 7, 10))

    assert len(provider.calls) == 2
    task = db.scalar(select(AiTask).order_by(AiTask.id.desc()))
    assert task is not None and task.status == "failed"
    assert "Expecting value" in (task.error_message or "")


def test_weekly_provider_output_requires_matching_total():
    with pytest.raises(ValueError, match="total_score"):
        validate_provider_output(
            "weekly_score",
            {
                "total_score": 71,
                "level": "达标踏实",
                "summary": "整体稳定",
                "dimension_scores": {
                    "产出与结果": {"score": 28, "full": 40},
                    "问题方案质量": {"score": 22, "full": 30},
                    "工作饱和度": {"score": 22, "full": 30},
                },
            },
        )


def test_generate_weekly_score_uses_previous_complete_week(
    db, user, objective, patch_provider
):
    report = DailyReport(user_id=user.id, report_date=date(2026, 7, 1), status="draft")
    db.add(report)
    db.flush()
    db.add_all(
        [
            DailyTask(
                report_id=report.id,
                user_id=user.id,
                task_time=time(9, 0),
                content="完成方案A",
                note="形成初步结论",
                is_done=True,
            ),
            ProblemSolution(
                report_id=report.id,
                user_id=user.id,
                problem_text="加载性能下降",
                solution_html="<p>定位慢查询并建立索引</p>",
            ),
        ]
    )
    db.commit()
    patch_provider(
        {
            "total_score": 78,
            "level": "明显出色",
            "summary": "推动了方案A，问题分析扎实。",
            "dimension_scores": {
                "产出与结果": {"score": 31, "full": 40, "note": "形成初步结论"},
                "问题方案质量": {"score": 24, "full": 30, "note": "定位慢查询"},
                "工作饱和度": {"score": 23, "full": 30, "note": "事务量较饱满"},
            },
            "key_achievements": ["完成方案A"],
            "concerns": ["部分日期无日报"],
            "manager_hint": "关注记录完整性",
        }
    )
    service = AiService(db, user)

    first = service.generate_weekly_score(date(2026, 7, 10))
    second = service.generate_weekly_score(date(2026, 7, 10))

    assert first.id == second.id
    assert first.week_start == date(2026, 6, 29)
    assert first.week_end == date(2026, 7, 5)
    assert first.total_score == 78
    assert db.scalar(select(func.count(WeeklyScore.id))) == 1
    task = db.scalar(
        select(AiTask).where(AiTask.task_type == "weekly_score").order_by(AiTask.id.desc())
    )
    assert task is not None
    context = task.input_json
    assert "2026-07-01" in context["weekly_reports"]
    assert "形成初步结论" in context["weekly_reports"]
    assert "定位慢查询并建立索引" in context["weekly_problems"]
    assert "2026-07-10" not in context["weekly_reports"]
    assert "提升指标A" in context["okr_content"]
