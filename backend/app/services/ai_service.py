from __future__ import annotations

import asyncio
import calendar
import json
import re
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.ai import (
    AiFeatureFlags,
    AiTask,
    AiUserMemory,
    DailyScore,
    DailySuggestion,
    MonthlyReportScore,
    OkrReview,
    PromptConfig,
    WeeklyScore,
)
from app.models.daily import DailyReport, DailyTask, ProblemSolution
from app.models.okr import MonthlyReportSection, OkrObjective
from app.models.traffic import TrafficMetric, TrafficMetricValue
from app.models.user import User
from app.core.security import utcnow
from app.schemas.ai_provider import validate_provider_output
from app.services.ai.defaults import (
    DEFAULT_NAMES,
    DEFAULT_TEMPLATES,
    DEFAULT_VARIABLES,
    PROMPT_TYPES,
    VARIABLE_LABELS,
)
from app.services.ai.factory import build_provider
from app.services.ai.provider import AiProviderError, AiProviderNotConfigured
from app.utils.dates import last_completed_week_start
from app.utils.dates import month_bounds, working_days_in

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def _strip_html(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"<[^>]+>", " ", value).strip()


def _parse_json(content: str) -> dict:
    """Parse model output as JSON, tolerating markdown code fences."""
    text = content.strip()
    match = _JSON_FENCE.search(text)
    if match:
        text = match.group(1)
    return json.loads(text)


# Fixed display order for the three daily-score dimensions.
_DIM_ORDER = ("importance_quality", "problem_solution_quality", "work_saturation")
_WEEKLY_DIM_ORDER = ("产出与结果", "问题方案质量", "工作饱和度")
_OKR_QUALITY_DIM_ORDER = ("O的价值", "KR支撑度", "工作饱和度")
_MONTHLY_REPORT_DIM_ORDER = (
    "复盘与思考深度",
    "工作饱和度",
    "真实性与一致性",
    "业绩与目标达成",
)


def _normalize_dimensions(dims) -> list[dict]:
    """Coerce the model's dimensions into the stored [{name,score,full,comment}]
    shape. Accepts the new object form (keyed by dimension) or a legacy list."""
    out: list[dict] = []
    if isinstance(dims, dict):
        keys = list(_DIM_ORDER) + [k for k in dims if k not in _DIM_ORDER]
        for key in keys:
            d = dims.get(key)
            if not isinstance(d, dict):
                continue
            out.append(
                {
                    "name": d.get("label") or key,
                    "score": int(d.get("score", 0) or 0),
                    "full": int(d.get("max", d.get("full", 0)) or 0),
                    "comment": d.get("note") or d.get("comment"),
                }
            )
    elif isinstance(dims, list):
        for d in dims:
            if not isinstance(d, dict):
                continue
            out.append(
                {
                    "name": d.get("name") or d.get("label") or "",
                    "score": int(d.get("score", 0) or 0),
                    "full": int(d.get("full", d.get("max", 0)) or 0),
                    "comment": d.get("comment") or d.get("note"),
                }
            )
    return out


def _normalize_weekly_dimensions(dims) -> list[dict]:
    if not isinstance(dims, dict):
        return []
    return [
        {
            "name": name,
            "score": int(dims[name].get("score", 0) or 0),
            "full": int(dims[name].get("full", 0) or 0),
            "comment": dims[name].get("note"),
        }
        for name in _WEEKLY_DIM_ORDER
        if isinstance(dims.get(name), dict)
    ]


def _normalize_okr_quality_dimensions(dims) -> list[dict]:
    if not isinstance(dims, dict):
        return []
    return [
        {
            "name": name,
            "score": int(dims[name].get("score", 0) or 0),
            "full": int(dims[name].get("full", 0) or 0),
            "comment": dims[name].get("note"),
        }
        for name in _OKR_QUALITY_DIM_ORDER
        if isinstance(dims.get(name), dict)
    ]


def _normalize_monthly_report_dimensions(dims) -> list[dict]:
    if not isinstance(dims, dict):
        return []
    return [
        {
            "name": name,
            "score": int(dims[name].get("score", 0) or 0),
            "full": int(dims[name].get("full", 0) or 0),
            "comment": dims[name].get("note"),
        }
        for name in _MONTHLY_REPORT_DIM_ORDER
        if isinstance(dims.get(name), dict)
    ]


def _dedupe_extend(base: list, additions) -> list:
    """Append new non-empty strings not already present (trimmed compare)."""
    result = list(base)
    seen = {s.strip() for s in result if isinstance(s, str)}
    for item in additions or []:
        if isinstance(item, str) and item.strip() and item.strip() not in seen:
            result.append(item.strip())
            seen.add(item.strip())
    return result


class AiService:
    """Orchestrates AI generation: gather context -> render prompt -> call
    provider -> parse -> persist -> record ai_tasks. All provider failures are
    raised as AiProviderError so the API layer can render a friendly state."""

    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    # ---- feature flags / prompts -------------------------------------

    def get_flags(self) -> AiFeatureFlags:
        row = self.db.scalar(
            select(AiFeatureFlags).where(
                AiFeatureFlags.id == 1, AiFeatureFlags.deleted_at.is_(None)
            )
        )
        if row is None:
            row = AiFeatureFlags(id=1)
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def get_prompt(self, prompt_type: str) -> PromptConfig:
        row = self.db.scalar(
            select(PromptConfig).where(
                PromptConfig.prompt_type == prompt_type,
                PromptConfig.deleted_at.is_(None),
            )
        )
        if row is None:
            row = PromptConfig(
                prompt_type=prompt_type,
                name=DEFAULT_NAMES.get(prompt_type, prompt_type),
                template_content=DEFAULT_TEMPLATES.get(prompt_type, ""),
                version="v1",
                variables_json=list(DEFAULT_VARIABLES.get(prompt_type, [])),
            )
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def _build_prompt(
        self, template: str, context: dict[str, str], selected: list[str]
    ) -> tuple[str, dict[str, str]]:
        """Compose the final prompt: template body + a 【数据】 block built from the
        admin-selected variables. Returns (prompt_text, used_context) so the task
        audit records only the data actually sent to the model."""
        used = {key: context.get(key, "") for key in selected if key in context}
        if not used:
            return template, used
        lines = [f"【{VARIABLE_LABELS.get(key, key)}】\n{value or '（无）'}" for key, value in used.items()]
        return template + "\n\n以下是相关数据：\n\n" + "\n\n".join(lines), used

    # ---- provider call + task audit ----------------------------------

    def _run_chat(
        self,
        *,
        task_type: str,
        prompt: PromptConfig,
        prompt_text: str,
        variables: dict[str, str],
        ref_date: date | None = None,
        ref_month: str | None = None,
        max_tokens: int = 1500,
        system_prompt: str | None = None,
    ) -> tuple[dict, AiTask]:
        task = AiTask(
            user_id=self.user.id,
            task_type=task_type,
            status="running",
            input_json=variables,
            model=None,
            prompt_config_id=prompt.id,
            ref_date=ref_date,
            ref_month=ref_month,
            started_at=utcnow(),
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)

        try:
            provider, model = build_provider(self.db)
            task.model = model
            self.db.commit()
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt_text})
            response = asyncio.run(
                provider.chat(model, messages, json_mode=True, max_tokens=max_tokens)
            )
            try:
                parsed = validate_provider_output(task_type, _parse_json(response.content))
            except (json.JSONDecodeError, ValueError):
                retry_messages = messages + [
                    {"role": "assistant", "content": response.content},
                    {
                        "role": "user",
                        "content": (
                            "上一次输出不是完整且符合字段约束的合法 JSON。请严格按规定结构"
                            "重新输出完整、精简的 JSON，只保留规定字段，不要 markdown，不要解释。"
                        ),
                    },
                ]
                response = asyncio.run(
                    provider.chat(
                        model,
                        retry_messages,
                        json_mode=True,
                        max_tokens=max_tokens,
                    )
                )
                parsed = validate_provider_output(task_type, _parse_json(response.content))
        except (AiProviderError, json.JSONDecodeError, ValueError) as exc:
            task.status = "failed"
            task.error_message = str(exc)[:500]
            task.finished_at = utcnow()
            self.db.commit()
            if isinstance(exc, AiProviderNotConfigured):
                raise
            raise AiProviderError(str(exc)) from exc

        task.status = "succeeded"
        task.output_json = parsed
        task.finished_at = utcnow()
        self.db.commit()
        self.db.refresh(task)
        return parsed, task

    # ---- context builders --------------------------------------------

    def _daily_context(self, report_date: date, user_id: int) -> dict[str, str]:
        report = self.db.scalar(
            select(DailyReport)
            .options(selectinload(DailyReport.tasks), selectinload(DailyReport.problems))
            .where(
                DailyReport.user_id == user_id,
                DailyReport.report_date == report_date,
                DailyReport.deleted_at.is_(None),
            )
        )
        checklist = ""
        problems = ""
        user_notes = ""
        if report is not None:
            tasks = sorted(
                (t for t in report.tasks if t.deleted_at is None),
                key=lambda t: (t.sort_order, t.task_time),
            )
            checklist = "\n".join(
                f"- [{'✓' if t.is_done else ' '}] {t.task_time.strftime('%H:%M')} {t.content}"
                for t in tasks
            )
            user_notes = "\n".join(
                f"- 「{t.content}」：{t.note.strip()}"
                for t in tasks
                if t.note and t.note.strip()
            )
            probs = [p for p in report.problems if p.deleted_at is None]
            problems = "\n".join(
                f"- 问题：{p.problem_text}\n  方案：{_strip_html(p.solution_html)}" for p in probs
            )
        month = report_date.strftime("%Y-%m")
        return {
            "date": report_date.strftime("%Y-%m-%d"),
            "checklist": checklist,
            "problems": problems,
            "user_notes": user_notes,
            "okr_content": self._okr_text(month, user_id),
            "memory": self._score_memory(report_date, user_id),
        }

    def _okr_text(self, month: str, user_id: int) -> str:
        objectives = self.db.scalars(
            select(OkrObjective)
            .options(selectinload(OkrObjective.key_results))
            .where(
                OkrObjective.user_id == user_id,
                OkrObjective.month == month,
                OkrObjective.deleted_at.is_(None),
            )
            .order_by(OkrObjective.sort_order)
        ).all()
        lines: list[str] = []
        for obj in objectives:
            lines.append(f"目标：{obj.title}（进度 {obj.progress}%）")
            for kr in sorted(obj.key_results, key=lambda k: k.sort_order):
                if kr.deleted_at is not None:
                    continue
                lines.append(f"  - KR：{kr.title}；人工标记进度 {kr.progress}%")
        return "\n".join(lines)

    def _weekly_context(
        self, week_start: date, week_end: date, user_id: int
    ) -> dict[str, str]:
        reports = self.db.scalars(
            select(DailyReport)
            .options(selectinload(DailyReport.tasks), selectinload(DailyReport.problems))
            .where(
                DailyReport.user_id == user_id,
                DailyReport.report_date >= week_start,
                DailyReport.report_date <= week_end,
                DailyReport.deleted_at.is_(None),
            )
            .order_by(DailyReport.report_date)
        ).all()
        by_date = {report.report_date: report for report in reports}
        weekday_names = "一二三四五六日"
        report_sections: list[str] = []
        problem_sections: list[str] = []

        for offset in range(7):
            current = week_start + timedelta(days=offset)
            heading = f"【{current.isoformat()} 周{weekday_names[current.weekday()]}】"
            report = by_date.get(current)
            if report is None:
                report_sections.append(f"{heading}\n- 无日报记录")
                problem_sections.append(f"{heading}\n- 无问题记录")
                continue

            tasks = sorted(
                (task for task in report.tasks if task.deleted_at is None),
                key=lambda task: (task.sort_order, task.task_time),
            )
            task_lines = []
            for task in tasks:
                line = (
                    f"- {task.task_time.strftime('%H:%M')} "
                    f"[{'已完成' if task.is_done else '未完成'}] {task.content}"
                )
                if task.note and task.note.strip():
                    line += f"；员工标注：{task.note.strip()}"
                task_lines.append(line)
            report_sections.append(
                heading + "\n" + ("\n".join(task_lines) if task_lines else "- 无工作事项记录")
            )

            problems = sorted(
                (problem for problem in report.problems if problem.deleted_at is None),
                key=lambda problem: problem.sort_order,
            )
            problem_lines = [
                f"- 问题：{problem.problem_text}\n  方案：{_strip_html(problem.solution_html) or '未填写'}"
                for problem in problems
            ]
            problem_sections.append(
                heading + "\n" + ("\n".join(problem_lines) if problem_lines else "- 无问题记录")
            )

        return {
            "weekly_reports": "\n\n".join(report_sections),
            "weekly_problems": "\n\n".join(problem_sections),
            "okr_content": self._okr_text(week_end.strftime("%Y-%m"), user_id),
        }

    def _okr_quality_text(self, month: str, user_id: int) -> str:
        """OKR-writing input without completion progress or current values."""
        objectives = self.db.scalars(
            select(OkrObjective)
            .options(selectinload(OkrObjective.key_results))
            .where(
                OkrObjective.user_id == user_id,
                OkrObjective.month == month,
                OkrObjective.deleted_at.is_(None),
            )
            .order_by(OkrObjective.sort_order)
        ).all()
        lines: list[str] = []
        for objective in objectives:
            lines.append(f"O：{objective.title}")
            for kr in sorted(objective.key_results, key=lambda item: item.sort_order):
                if kr.deleted_at is not None:
                    continue
                lines.append(f"  - KR：{kr.title}")
        return "\n".join(lines) or "（当月未填写 OKR）"

    def _get_user_memory(self, user_id: int) -> AiUserMemory:
        row = self.db.scalar(
            select(AiUserMemory).where(
                AiUserMemory.user_id == user_id,
                AiUserMemory.deleted_at.is_(None),
            )
        )
        if row is None:
            row = AiUserMemory(user_id=user_id)
            self.db.add(row)
            self.db.flush()
        return row

    def _score_memory(self, report_date: date, user_id: int, days: int = 5) -> str:
        """Structured memory block for the daily-score engine: recent score
        trajectory (live from daily_scores) + accumulated recurring notes."""
        rows = self.db.execute(
            select(DailyScore.score_date, DailyScore.total_score, DailyScore.level)
            .where(
                DailyScore.user_id == user_id,
                DailyScore.score_date < report_date,
                DailyScore.deleted_at.is_(None),
            )
            .order_by(DailyScore.score_date.desc())
            .limit(days)
        ).all()
        # recent_scores[0] = most recent, per the template's score_delta rule.
        recent = [
            {"date": r[0].isoformat(), "total_score": r[1], "level": r[2]} for r in rows
        ]
        mem = self._get_user_memory(user_id)
        payload = {
            "recent_scores": recent,
            "recurring_strengths": list(mem.recurring_strengths_json or []),
            "recurring_issues": list(mem.recurring_issues_json or []),
            "manager_hints": list(mem.manager_hints_json or []),
            "last_summary": mem.last_summary or "",
        }
        return json.dumps(payload, ensure_ascii=False, indent=2)

    # ---- daily score --------------------------------------------------

    def generate_daily_score(self, report_date: date, user_id: int | None = None) -> DailyScore:
        uid = user_id or self.user.id
        prompt = self.get_prompt("daily_score")
        context = self._daily_context(report_date, uid)
        prompt_text, variables = self._build_prompt(
            prompt.template_content, context, prompt.variables_json
        )
        parsed, task = self._run_chat(
            task_type="daily_score",
            prompt=prompt,
            prompt_text=prompt_text,
            variables=variables,
            ref_date=report_date,
            max_tokens=4096,
        )

        dims = _normalize_dimensions(parsed.get("dimensions"))
        total = int(parsed.get("total_score") or sum(d["score"] for d in dims))
        prev = self.db.scalar(
            select(DailyScore.total_score)
            .where(
                DailyScore.user_id == uid,
                DailyScore.score_date < report_date,
                DailyScore.deleted_at.is_(None),
            )
            .order_by(DailyScore.score_date.desc())
            .limit(1)
        )
        delta = (total - int(prev)) if prev is not None else None

        row = self.db.scalar(
            select(DailyScore).where(
                DailyScore.user_id == uid,
                DailyScore.score_date == report_date,
                DailyScore.deleted_at.is_(None),
            )
        )
        if row is None:
            row = DailyScore(user_id=uid, score_date=report_date)
            self.db.add(row)
        row.total_score = total
        row.level = parsed.get("level")
        row.score_delta = delta
        row.trend_note = parsed.get("trend_note")
        row.one_line_review = parsed.get("one_line_review")
        row.dimensions_json = dims
        okr_outside = parsed.get("okr_outside_high_value")
        row.okr_outside_high_value_json = okr_outside or []
        # manager_hint now lives inside the okr_outside object; fall back to a
        # top-level key for backward compatibility.
        if isinstance(okr_outside, dict):
            row.manager_hint = okr_outside.get("manager_hint") or parsed.get("manager_hint")
        else:
            row.manager_hint = parsed.get("manager_hint")
        row.okr_clarity_warning = parsed.get("okr_clarity_warning")
        row.ai_task_id = task.id
        row.generated_at = utcnow()

        self._apply_memory_update(uid, parsed.get("memory_update"), row.manager_hint)
        self.db.commit()
        self.db.refresh(row)
        return row

    def _apply_memory_update(
        self, user_id: int, update: dict | None, manager_hint: str | None
    ) -> None:
        """Fold the model's memory_update block back into AiUserMemory: extend
        recurring strengths/issues, drop resolved issues, accrue manager hints,
        and refresh the running profile summary."""
        mem = self._get_user_memory(user_id)
        update = update or {}

        mem.recurring_strengths_json = _dedupe_extend(
            mem.recurring_strengths_json or [], update.get("recurring_strengths_delta")
        )
        issues = _dedupe_extend(
            mem.recurring_issues_json or [], update.get("recurring_issues_delta")
        )
        resolved = {
            s.strip()
            for s in (update.get("resolved_issues") or [])
            if isinstance(s, str)
        }
        mem.recurring_issues_json = [i for i in issues if i.strip() not in resolved]

        if manager_hint and manager_hint.strip():
            # Keep the most recent 10 hints.
            hints = _dedupe_extend(mem.manager_hints_json or [], [manager_hint])
            mem.manager_hints_json = hints[-10:]

        profile = update.get("profile_note")
        if isinstance(profile, str) and profile.strip():
            mem.last_summary = profile.strip()

    def get_daily_score(self, report_date: date, user_id: int | None = None) -> DailyScore | None:
        uid = user_id or self.user.id
        return self.db.scalar(
            select(DailyScore).where(
                DailyScore.user_id == uid,
                DailyScore.score_date == report_date,
                DailyScore.deleted_at.is_(None),
            )
        )

    def latest_daily_score(self, user_id: int) -> DailyScore | None:
        return self.db.scalar(
            select(DailyScore)
            .where(DailyScore.user_id == user_id, DailyScore.deleted_at.is_(None))
            .order_by(DailyScore.score_date.desc())
            .limit(1)
        )

    # ---- weekly score -------------------------------------------------

    def generate_weekly_score(
        self, anchor_date: date, user_id: int | None = None
    ) -> WeeklyScore:
        uid = user_id or self.user.id
        week_start = last_completed_week_start(anchor_date)
        week_end = week_start + timedelta(days=6)
        prompt = self.get_prompt("weekly_score")
        context = self._weekly_context(week_start, week_end, uid)
        prompt_text, variables = self._build_prompt(
            prompt.template_content, context, prompt.variables_json
        )
        parsed, task = self._run_chat(
            task_type="weekly_score",
            prompt=prompt,
            prompt_text=prompt_text,
            variables=variables,
            ref_date=week_end,
            max_tokens=4096,
        )

        dimensions = _normalize_weekly_dimensions(parsed.get("dimension_scores"))
        row = self.db.scalar(
            select(WeeklyScore).where(
                WeeklyScore.user_id == uid,
                WeeklyScore.week_start == week_start,
                WeeklyScore.deleted_at.is_(None),
            )
        )
        if row is None:
            row = WeeklyScore(user_id=uid, week_start=week_start, week_end=week_end)
            self.db.add(row)
        row.week_end = week_end
        row.total_score = int(parsed["total_score"])
        row.level = parsed.get("level")
        row.summary = parsed.get("summary")
        row.dimensions_json = dimensions
        row.key_achievements_json = list(parsed.get("key_achievements") or [])
        row.concerns_json = list(parsed.get("concerns") or [])
        row.manager_hint = parsed.get("manager_hint")
        row.ai_task_id = task.id
        row.generated_at = utcnow()
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_weekly_score(
        self, anchor_date: date, user_id: int | None = None
    ) -> WeeklyScore | None:
        uid = user_id or self.user.id
        week_start = last_completed_week_start(anchor_date)
        return self.db.scalar(
            select(WeeklyScore).where(
                WeeklyScore.user_id == uid,
                WeeklyScore.week_start == week_start,
                WeeklyScore.deleted_at.is_(None),
            )
        )

    # ---- daily suggestions -------------------------------------------

    def _company_text_snippets(self, suggestion_date: date, user: User) -> str:
        cutoff = suggestion_date - timedelta(days=30)
        candidates: list[tuple[int, date, str]] = []

        reports = self.db.scalars(
            select(DailyReport)
            .options(selectinload(DailyReport.tasks), selectinload(DailyReport.problems))
            .where(
                DailyReport.report_date >= cutoff,
                DailyReport.report_date <= suggestion_date,
                DailyReport.deleted_at.is_(None),
            )
            .order_by(DailyReport.report_date.desc())
        ).all()
        author_ids = {report.user_id for report in reports}
        authors = {
            row.id: row.name
            for row in self.db.scalars(
                select(User).where(User.id.in_(author_ids), User.deleted_at.is_(None))
            ).all()
        } if author_ids else {}
        for report in reports:
            author = authors.get(report.user_id, f"用户{report.user_id}")
            for task in report.tasks:
                if task.deleted_at is not None or (
                    task.is_private and report.user_id != user.id
                ):
                    continue
                text = task.content.strip()
                if task.note and task.note.strip():
                    text += f"；标注：{task.note.strip()}"
                priority = 2 if user.name in text else (1 if report.user_id == user.id else 0)
                candidates.append(
                    (priority, report.report_date, f"{author} {report.report_date} 日报：{text}")
                )
            for problem in report.problems:
                if problem.deleted_at is not None:
                    continue
                text = (
                    f"问题：{problem.problem_text}；方案："
                    f"{_strip_html(problem.solution_html) or '未填写'}"
                )
                priority = 2 if user.name in text else (1 if report.user_id == user.id else 0)
                candidates.append(
                    (priority, report.report_date, f"{author} {report.report_date}：{text}")
                )

        traffic_rows = self.db.execute(
            select(TrafficMetricValue, TrafficMetric, User)
            .join(TrafficMetric, TrafficMetric.id == TrafficMetricValue.metric_id)
            .join(User, User.id == TrafficMetric.owner_id)
            .where(
                TrafficMetricValue.week_end >= cutoff,
                TrafficMetricValue.week_start <= suggestion_date,
                TrafficMetricValue.note.is_not(None),
                TrafficMetricValue.deleted_at.is_(None),
                TrafficMetric.deleted_at.is_(None),
                User.deleted_at.is_(None),
            )
        ).all()
        for value, metric, owner in traffic_rows:
            note = (value.note or "").strip()
            if not note:
                continue
            text = f"{owner.name} {value.week_end} 红绿灯「{metric.name}」备注：{note}"
            priority = 2 if user.name in text else (1 if owner.id == user.id else 0)
            candidates.append((priority, value.week_end, text))

        month = suggestion_date.strftime("%Y-%m")
        sections = self.db.execute(
            select(MonthlyReportSection, User)
            .join(User, User.id == MonthlyReportSection.user_id)
            .where(
                MonthlyReportSection.month == month,
                MonthlyReportSection.deleted_at.is_(None),
                User.deleted_at.is_(None),
            )
        ).all()
        for section, author in sections:
            content = _strip_html(section.content_html)
            if not content:
                continue
            text = f"{author.name} {month} 文档「{section.title}」：{content[:600]}"
            priority = 2 if user.name in text else (1 if author.id == user.id else 0)
            candidates.append((priority, suggestion_date, text))

        candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        snippets = [f"- {text[:800]}" for _, _, text in candidates[:30]]
        return "\n".join(snippets) or "（近 30 天暂无可用的公司文字片段）"

    def _suggestion_okr_text(self, suggestion_date: date, user_id: int) -> str:
        month = suggestion_date.strftime("%Y-%m")
        _, month_days = calendar.monthrange(suggestion_date.year, suggestion_date.month)
        days_left = month_days - suggestion_date.day
        objectives = self.db.scalars(
            select(OkrObjective)
            .options(selectinload(OkrObjective.key_results))
            .where(
                OkrObjective.user_id == user_id,
                OkrObjective.month == month,
                OkrObjective.deleted_at.is_(None),
            )
            .order_by(OkrObjective.sort_order)
        ).all()
        lines: list[str] = []
        for objective in objectives:
            lines.append(f"O：{objective.title}（整体进度 {objective.progress}%）")
            for kr in sorted(objective.key_results, key=lambda item: item.sort_order):
                if kr.deleted_at is not None:
                    continue
                last_update = kr.updated_at.date()
                stalled_days = max((suggestion_date - last_update).days, 0)
                lines.append(
                    f"  - KR：{kr.title}；人工标记进度 {kr.progress}%；月底临期 {days_left} 天；"
                    f"停滞 {stalled_days} 天；最近更新 {last_update.isoformat()}"
                )
        return "\n".join(lines) or "（当前用户本月未填写 OKR）"

    def _manual_suggestion_context(self, user_id: int, suggestion_date: date) -> str:
        tasks = self.db.scalars(
            select(AiTask)
            .where(
                AiTask.user_id == user_id,
                AiTask.task_type == "daily_suggestion",
                AiTask.status == "succeeded",
                AiTask.ref_date <= suggestion_date,
                AiTask.deleted_at.is_(None),
            )
            .order_by(AiTask.id.desc())
            .limit(10)
        ).all()
        entries: list[str] = []
        for task in tasks:
            context = task.input_json if isinstance(task.input_json, dict) else {}
            supplement = context.get("realtime_supplement")
            if isinstance(supplement, str) and supplement.strip():
                entries.append(f"- {task.ref_date}: {supplement.strip()}")
        return "\n".join(entries) or "（暂无此前补充的等待、依赖或解锁信息）"

    def _suggestion_context(
        self,
        suggestion_date: date,
        user_id: int,
        realtime_supplement: str = "",
    ) -> dict[str, str]:
        user = self.db.scalar(
            select(User).where(User.id == user_id, User.deleted_at.is_(None))
        )
        if user is None:
            raise ValueError("User not found")
        _, month_days = calendar.monthrange(suggestion_date.year, suggestion_date.month)
        role_label = "管理者" if user.role == "owner" else "员工"
        daily_context = self._daily_context(suggestion_date, user_id)
        return {
            "current_user": (
                f"姓名：{user.name}\n角色：{user.role}（{role_label}）\n"
                f"今天日期：{suggestion_date.isoformat()}，距本月结束还有 "
                f"{month_days - suggestion_date.day} 天"
            ),
            "company_text_snippets": self._company_text_snippets(suggestion_date, user),
            "my_okrs": self._suggestion_okr_text(suggestion_date, user_id),
            "my_dependencies": (
                "（当前系统暂无结构化、人工确认的 KR 依赖关系；只能在公司文字明确提及"
                "依赖时谨慎推断，不得编造上下游关系）"
            ),
            "my_checklist_today": daily_context["checklist"] or "（今天清单为空）",
            "my_manual_context": self._manual_suggestion_context(user_id, suggestion_date),
            "realtime_supplement": realtime_supplement.strip() or "（本次无补充）",
            "prefs": "（当前系统暂无已记录的历史取舍偏好）",
        }

    def generate_suggestions(
        self,
        suggestion_date: date,
        user_id: int | None = None,
        realtime_supplement: str = "",
    ) -> list[DailySuggestion]:
        uid = user_id or self.user.id
        prompt = self.get_prompt("daily_suggestion")
        context = self._suggestion_context(suggestion_date, uid, realtime_supplement)
        prompt_text, variables = self._build_prompt(
            "", context, prompt.variables_json
        )
        parsed, _task = self._run_chat(
            task_type="daily_suggestion",
            prompt=prompt,
            prompt_text=prompt_text,
            variables=variables,
            ref_date=suggestion_date,
            max_tokens=3000,
            system_prompt=prompt.template_content,
        )

        # Regenerating replaces the previous pending set for that day.
        existing = self.db.scalars(
            select(DailySuggestion).where(
                DailySuggestion.user_id == uid,
                DailySuggestion.suggestion_date == suggestion_date,
                DailySuggestion.status == "pending",
                DailySuggestion.deleted_at.is_(None),
            )
        ).all()
        for row in existing:
            row.deleted_at = utcnow()

        items: list[DailySuggestion] = []
        for entry in parsed.get("suggestions") or []:
            content = (entry.get("title") or "").strip()
            if not content:
                continue
            row = DailySuggestion(
                user_id=uid,
                suggestion_date=suggestion_date,
                content=content,
                reason=entry.get("reason"),
                suggestion_type=entry.get("type") or "amber",
                linked_json=entry.get("linked") or {},
                needs_info=bool(entry.get("needs_info")),
                ask_json=entry.get("ask") or {},
                source_context_json=variables,
                status="pending",
            )
            self.db.add(row)
            items.append(row)
        self.db.commit()
        for row in items:
            self.db.refresh(row)
        return items

    def latest_suggestion_summary(
        self, suggestion_date: date, user_id: int | None = None
    ) -> str:
        uid = user_id or self.user.id
        task = self.db.scalar(
            select(AiTask)
            .where(
                AiTask.user_id == uid,
                AiTask.task_type == "daily_suggestion",
                AiTask.ref_date == suggestion_date,
                AiTask.status == "succeeded",
                AiTask.deleted_at.is_(None),
            )
            .order_by(AiTask.id.desc())
            .limit(1)
        )
        output = task.output_json if task and isinstance(task.output_json, dict) else {}
        summary = output.get("summary")
        return summary.strip() if isinstance(summary, str) else ""

    def list_suggestions(self, suggestion_date: date) -> list[DailySuggestion]:
        return list(
            self.db.scalars(
                select(DailySuggestion)
                .where(
                    DailySuggestion.user_id == self.user.id,
                    DailySuggestion.suggestion_date == suggestion_date,
                    DailySuggestion.status == "pending",
                    DailySuggestion.deleted_at.is_(None),
                )
                .order_by(DailySuggestion.id)
            ).all()
        )

    def get_suggestion(self, suggestion_id: int) -> DailySuggestion | None:
        return self.db.scalar(
            select(DailySuggestion).where(
                DailySuggestion.id == suggestion_id,
                DailySuggestion.user_id == self.user.id,
                DailySuggestion.deleted_at.is_(None),
            )
        )

    def accept_suggestion(self, suggestion: DailySuggestion) -> DailySuggestion:
        """Turn a suggestion into a DailyTask on the user's report for that day."""
        from datetime import time as _time

        if suggestion.status == "accepted" and suggestion.accepted_task_id is not None:
            return suggestion
        if suggestion.status != "pending":
            raise ValueError("Only pending suggestions can be accepted")

        report = self.db.scalar(
            select(DailyReport).where(
                DailyReport.user_id == self.user.id,
                DailyReport.report_date == suggestion.suggestion_date,
                DailyReport.deleted_at.is_(None),
            )
        )
        if report is None:
            report = DailyReport(
                user_id=self.user.id,
                report_date=suggestion.suggestion_date,
                status="draft",
                created_by=self.user.id,
                updated_by=self.user.id,
            )
            self.db.add(report)
            self.db.flush()
        next_sort = self.db.scalar(
            select(DailyTask.sort_order)
            .where(DailyTask.report_id == report.id, DailyTask.deleted_at.is_(None))
            .order_by(DailyTask.sort_order.desc())
            .limit(1)
        )
        task = DailyTask(
            report_id=report.id,
            user_id=self.user.id,
            task_time=_time(9, 0),
            content=suggestion.content,
            source="suggestion",
            sort_order=(int(next_sort) + 1) if next_sort is not None else 0,
            created_by=self.user.id,
            updated_by=self.user.id,
        )
        self.db.add(task)
        self.db.flush()
        suggestion.status = "accepted"
        suggestion.accepted_task_id = task.id
        self.db.commit()
        self.db.refresh(suggestion)
        return suggestion

    def reject_suggestion(self, suggestion: DailySuggestion) -> None:
        if suggestion.status == "rejected":
            return
        if suggestion.status != "pending":
            raise ValueError("Only pending suggestions can be rejected")
        suggestion.status = "rejected"
        self.db.commit()

    # ---- okr review ---------------------------------------------------

    def generate_okr_review(self, month: str, user_id: int | None = None) -> OkrReview:
        uid = user_id or self.user.id
        prompt = self.get_prompt("okr_quality")
        context = {
            "month": month,
            "okr_content": self._okr_quality_text(month, uid),
        }
        prompt_text, variables = self._build_prompt(
            prompt.template_content, context, prompt.variables_json
        )
        parsed, task = self._run_chat(
            task_type="okr_quality",
            prompt=prompt,
            prompt_text=prompt_text,
            variables=variables,
            ref_month=month,
            max_tokens=3000,
        )

        row = self.db.scalar(
            select(OkrReview).where(
                OkrReview.user_id == uid,
                OkrReview.month == month,
                OkrReview.deleted_at.is_(None),
            )
        )
        if row is None:
            row = OkrReview(user_id=uid, month=month)
            self.db.add(row)
        row.quality_score = Decimal(str(parsed["total_score"]))
        row.level = parsed.get("level")
        row.summary = parsed.get("summary")
        row.dimensions_json = _normalize_okr_quality_dimensions(
            parsed.get("dimension_scores")
        )
        row.highlights_json = list(parsed.get("highlights") or [])
        row.optional_improvements_json = list(parsed.get("optional_improvements") or [])
        row.impact_on_daily_scoring = parsed.get("impact_on_daily_scoring")
        row.ai_task_id = task.id
        row.generated_at = utcnow()
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_okr_review(self, month: str, user_id: int | None = None) -> OkrReview | None:
        uid = user_id or self.user.id
        return self.db.scalar(
            select(OkrReview).where(
                OkrReview.user_id == uid,
                OkrReview.month == month,
                OkrReview.deleted_at.is_(None),
            )
        )

    def latest_okr_review(self, user_id: int) -> OkrReview | None:
        return self.db.scalar(
            select(OkrReview)
            .where(OkrReview.user_id == user_id, OkrReview.deleted_at.is_(None))
            .order_by(OkrReview.month.desc())
            .limit(1)
        )

    # ---- monthly report score ----------------------------------------

    def _monthly_report_score_context(self, month: str, user_id: int) -> dict[str, str]:
        start, end = month_bounds(month)
        reports = self.db.scalars(
            select(DailyReport)
            .options(selectinload(DailyReport.tasks), selectinload(DailyReport.problems))
            .where(
                DailyReport.user_id == user_id,
                DailyReport.report_date >= start,
                DailyReport.report_date <= end,
                DailyReport.deleted_at.is_(None),
            )
            .order_by(DailyReport.report_date)
        ).all()

        total_tasks = 0
        completed_tasks = 0
        problem_count = 0
        solution_count = 0
        updated_days = 0
        digest_sections: list[str] = []
        for report in reports:
            tasks = sorted(
                (task for task in report.tasks if task.deleted_at is None),
                key=lambda task: (task.sort_order, task.task_time),
            )
            problems = sorted(
                (problem for problem in report.problems if problem.deleted_at is None),
                key=lambda problem: problem.sort_order,
            )
            if not tasks and not problems:
                continue
            updated_days += 1
            total_tasks += len(tasks)
            completed_tasks += sum(1 for task in tasks if task.is_done)
            problem_count += len(problems)
            solution_count += sum(
                1 for problem in problems if _strip_html(problem.solution_html)
            )
            lines = [f"【{report.report_date.isoformat()}】"]
            lines.extend(
                (
                    f"- 清单 {task.task_time.strftime('%H:%M')} "
                    f"[{'已完成' if task.is_done else '未完成'}] {task.content}"
                    + (
                        f"；员工标注：{task.note.strip()}"
                        if task.note and task.note.strip()
                        else ""
                    )
                )
                for task in tasks
            )
            lines.extend(
                f"- 问题：{problem.problem_text}\n  解决方案："
                f"{_strip_html(problem.solution_html) or '未填写'}"
                for problem in problems
            )
            digest_sections.append("\n".join(lines))

        completion_rate = (
            round(completed_tasks / total_tasks * 100, 1) if total_tasks else 0
        )
        overview = (
            f"月份：{month}\n"
            f"工作日数量：{working_days_in(start, end)}\n"
            f"有内容的日报更新天数：{updated_days}\n"
            f"工作清单：共 {total_tasks} 条，完成 {completed_tasks} 条，完成率 {completion_rate}%\n"
            f"问题记录：{problem_count} 条，其中填写解决方案 {solution_count} 条"
        )

        sections = self.db.scalars(
            select(MonthlyReportSection)
            .where(
                MonthlyReportSection.user_id == user_id,
                MonthlyReportSection.month == month,
                MonthlyReportSection.deleted_at.is_(None),
            )
            .order_by(MonthlyReportSection.sort_order, MonthlyReportSection.id)
        ).all()
        report_content = "\n\n".join(
            f"【{section.title}】\n{_strip_html(section.content_html) or '（未填写）'}"
            for section in sections
        ) or "（本月月报暂无栏目内容）"

        return {
            "month_overview": overview,
            "daily_digest": "\n\n".join(digest_sections) or "（本月无日报内容）",
            "okr_content": self._okr_text(month, user_id) or "（本月未填写 OKR）",
            "monthly_report_content": report_content,
        }

    def generate_monthly_report_score(
        self, month: str, user_id: int | None = None
    ) -> MonthlyReportScore:
        uid = user_id or self.user.id
        prompt = self.get_prompt("monthly_report_score")
        context = self._monthly_report_score_context(month, uid)
        prompt_text, variables = self._build_prompt(
            prompt.template_content, context, prompt.variables_json
        )
        parsed, task = self._run_chat(
            task_type="monthly_report_score",
            prompt=prompt,
            prompt_text=prompt_text,
            variables=variables,
            ref_month=month,
            max_tokens=4096,
        )

        row = self.db.scalar(
            select(MonthlyReportScore).where(
                MonthlyReportScore.user_id == uid,
                MonthlyReportScore.month == month,
                MonthlyReportScore.deleted_at.is_(None),
            )
        )
        if row is None:
            row = MonthlyReportScore(user_id=uid, month=month)
            self.db.add(row)
        row.total_score = int(parsed["total_score"])
        row.summary = parsed.get("summary")
        row.dimensions_json = _normalize_monthly_report_dimensions(
            parsed.get("dimension_scores")
        )
        row.doubts_json = list(parsed.get("doubts") or [])
        row.suggestions_json = list(parsed.get("suggestions") or [])
        row.ai_task_id = task.id
        row.generated_at = utcnow()
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_monthly_report_score(
        self, month: str, user_id: int | None = None
    ) -> MonthlyReportScore | None:
        uid = user_id or self.user.id
        return self.db.scalar(
            select(MonthlyReportScore).where(
                MonthlyReportScore.user_id == uid,
                MonthlyReportScore.month == month,
                MonthlyReportScore.deleted_at.is_(None),
            )
        )

