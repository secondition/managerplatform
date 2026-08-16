"""Single-instance APScheduler jobs (design doc §12).

The recurring-task job always runs. AI jobs run in worker threads, are gated by
feature flags, and skip silently when the provider is unconfigured.
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta
from pathlib import Path
from typing import BinaryIO

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import and_, or_, select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ai import AiFeatureFlags, AiTask
from app.models.daily import DailyReport, DailyTask, ProblemSolution
from app.models.traffic import TrafficMetric, TrafficMetricAssignment, TrafficMetricValue
from app.models.user import User, UserPermission
from app.services.ai.provider import AiProviderError
from app.services.ai_service import AiService
from app.services.daily_service import materialize_recurring_tasks
from app.services.feishu_message_service import deliver_pending_feishu_notifications
from app.services.notification_service import NotificationService
from app.core.permissions import FEATURE_DAILY, FEATURE_TRAFFIC
from app.utils.dates import last_completed_week_start
from app.utils.time import local_today
from app.core.security import utcnow

logger = logging.getLogger("app.scheduler")

_scheduler: BackgroundScheduler | None = None
_scheduler_lock: BinaryIO | None = None
_LOCK_PATH = Path(__file__).resolve().parents[2] / "storage" / "scheduler.lock"


def _acquire_scheduler_lock() -> BinaryIO | None:
    _LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = _LOCK_PATH.open("a+b")
    if handle.seek(0, os.SEEK_END) == 0:
        handle.write(b"0")
        handle.flush()
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


def _release_scheduler_lock() -> None:
    global _scheduler_lock
    if _scheduler_lock is None:
        return
    try:
        _scheduler_lock.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(_scheduler_lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(_scheduler_lock.fileno(), fcntl.LOCK_UN)
    finally:
        _scheduler_lock.close()
        _scheduler_lock = None


def _active_users(db) -> list[User]:
    return list(
        db.scalars(select(User).where(User.status == "active", User.deleted_at.is_(None))).all()
    )


def _flags(db) -> AiFeatureFlags | None:
    return db.scalar(
        select(AiFeatureFlags).where(AiFeatureFlags.id == 1, AiFeatureFlags.deleted_at.is_(None))
    )


def generate_daily_scores_for_all_active_users() -> None:
    db = SessionLocal()
    try:
        flags = _flags(db)
        if flags is None or not flags.scheduler_enabled or not flags.daily_score_enabled:
            return
        today = local_today()
        for user in _active_users(db):
            try:
                AiService(db, user).generate_daily_score(today, user_id=user.id)
            except AiProviderError as exc:
                db.rollback()
                logger.warning("daily score skipped for user %s: %s", user.id, exc)
            except Exception:  # noqa: BLE001 — one user's failure must not abort the batch
                db.rollback()
                logger.exception("daily score failed for user %s", user.id)
    finally:
        db.close()


def generate_weekly_scores_for_all_active_users() -> None:
    db = SessionLocal()
    try:
        flags = _flags(db)
        if flags is None or not flags.scheduler_enabled or not flags.daily_score_enabled:
            return
        today = local_today()
        for user in _active_users(db):
            try:
                AiService(db, user).generate_weekly_score(today, user_id=user.id)
            except AiProviderError as exc:
                db.rollback()
                logger.warning("weekly score skipped for user %s: %s", user.id, exc)
            except Exception:  # noqa: BLE001
                db.rollback()
                logger.exception("weekly score failed for user %s", user.id)
    finally:
        db.close()


def generate_daily_suggestions_for_all_active_users() -> None:
    db = SessionLocal()
    try:
        flags = _flags(db)
        if flags is None or not flags.scheduler_enabled or not flags.daily_suggestion_enabled:
            return
        today = local_today()
        for user in _active_users(db):
            try:
                AiService(db, user).generate_suggestions(today, user_id=user.id)
            except AiProviderError as exc:
                db.rollback()
                logger.warning("daily suggestions skipped for user %s: %s", user.id, exc)
            except Exception:  # noqa: BLE001
                db.rollback()
                logger.exception("daily suggestions failed for user %s", user.id)
    finally:
        db.close()


def generate_okr_reviews_for_all_active_users() -> None:
    db = SessionLocal()
    try:
        flags = _flags(db)
        if flags is None or not flags.scheduler_enabled or not flags.okr_review_enabled:
            return
        month = local_today().strftime("%Y-%m")
        for user in _active_users(db):
            try:
                AiService(db, user).generate_okr_review(month, user_id=user.id)
            except AiProviderError as exc:
                db.rollback()
                logger.warning("okr review skipped for user %s: %s", user.id, exc)
            except Exception:  # noqa: BLE001
                db.rollback()
                logger.exception("okr review failed for user %s", user.id)
    finally:
        db.close()


def generate_monthly_report_scores_for_all_active_users() -> None:
    db = SessionLocal()
    try:
        flags = _flags(db)
        if flags is None or not flags.scheduler_enabled or not flags.okr_review_enabled:
            return
        month = local_today().strftime("%Y-%m")
        for user in _active_users(db):
            try:
                AiService(db, user).generate_monthly_report_score(month, user_id=user.id)
            except AiProviderError as exc:
                db.rollback()
                logger.warning("monthly report score skipped for user %s: %s", user.id, exc)
            except Exception:  # noqa: BLE001
                db.rollback()
                logger.exception("monthly report score failed for user %s", user.id)
    finally:
        db.close()


def cleanup_stale_ai_tasks() -> None:
    """Soft-delete finished ai_tasks older than 30 days."""
    db = SessionLocal()
    try:
        cutoff = utcnow() - timedelta(days=30)
        rows = db.scalars(
            select(AiTask).where(
                AiTask.deleted_at.is_(None),
                AiTask.finished_at.is_not(None),
                AiTask.finished_at < cutoff,
            )
        ).all()
        for row in rows:
            row.deleted_at = utcnow()
        db.commit()
    finally:
        db.close()


def materialize_recurring_daily_tasks() -> None:
    db = SessionLocal()
    try:
        created = materialize_recurring_tasks(db, local_today())
        if created:
            logger.info("materialized %s recurring daily tasks", created)
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("recurring daily task materialization failed")
    finally:
        db.close()


def _users_with_feature(db, permission: str) -> list[User]:
    return list(
        db.scalars(
            select(User)
            .join(UserPermission, UserPermission.user_id == User.id)
            .where(
                User.status == "active",
                User.deleted_at.is_(None),
                UserPermission.permission == permission,
                UserPermission.enabled.is_(True),
                UserPermission.deleted_at.is_(None),
            )
            .order_by(User.id)
        ).all()
    )


def notify_missing_daily_reports(check_date: date | None = None, slot: str = "1000") -> int:
    """Notify active daily users who have no own content for the date."""
    db = SessionLocal()
    created = 0
    try:
        target_date = check_date or local_today()
        users = _users_with_feature(db, FEATURE_DAILY)
        task_user_ids = set(
            db.scalars(
                select(DailyTask.user_id)
                .join(DailyReport, DailyReport.id == DailyTask.report_id)
                .where(
                    DailyReport.report_date == target_date,
                    DailyTask.deleted_at.is_(None),
                    DailyReport.deleted_at.is_(None),
                )
            ).all()
        )
        problem_user_ids = set(
            db.scalars(
                select(ProblemSolution.user_id)
                .join(DailyReport, DailyReport.id == ProblemSolution.report_id)
                .where(
                    DailyReport.report_date == target_date,
                    ProblemSolution.deleted_at.is_(None),
                    DailyReport.deleted_at.is_(None),
                )
            ).all()
        )
        for user in users:
            if user.id in task_user_ids or user.id in problem_user_ids:
                continue
            notification = NotificationService(db).notify(
                recipient=user,
                notification_type="daily.missing",
                title="日报尚未填写",
                body=f"你今天（{target_date.isoformat()}）还没有填写日报，请及时补充。",
                action_url=f"/daily?date={target_date.isoformat()}",
                dedupe_key=f"daily.missing:{user.id}:{target_date.isoformat()}:{slot}",
                metadata={"date": target_date.isoformat(), "slot": slot},
            )
            if notification is not None and notification.id is None:
                created += 1
        db.commit()
        return created
    except Exception:
        db.rollback()
        logger.exception("daily missing notification scan failed")
        return 0
    finally:
        db.close()


def notify_missing_weekly_metrics(target_week_start: date | None = None) -> int:
    """Aggregate missing values from the most recently completed traffic week."""
    db = SessionLocal()
    created = 0
    try:
        week_start = target_week_start or last_completed_week_start(local_today())
        rows = db.execute(
            select(
                TrafficMetricAssignment.assignee_id,
                TrafficMetric.id,
                TrafficMetric.name,
            )
            .join(TrafficMetric, TrafficMetric.id == TrafficMetricAssignment.metric_id)
            .join(User, User.id == TrafficMetricAssignment.assignee_id)
            .join(
                UserPermission,
                and_(
                    UserPermission.user_id == User.id,
                    UserPermission.permission == FEATURE_TRAFFIC,
                    UserPermission.enabled.is_(True),
                    UserPermission.deleted_at.is_(None),
                ),
            )
            .outerjoin(
                TrafficMetricValue,
                and_(
                    TrafficMetricValue.assignment_id == TrafficMetricAssignment.id,
                    TrafficMetricValue.week_start == week_start,
                    TrafficMetricValue.deleted_at.is_(None),
                ),
            )
            .where(
                TrafficMetricAssignment.effective_from <= week_start,
                TrafficMetricAssignment.deleted_at.is_(None),
                TrafficMetric.deleted_at.is_(None),
                User.status == "active",
                User.deleted_at.is_(None),
                or_(TrafficMetricValue.id.is_(None), TrafficMetricValue.value.is_(None)),
            )
            .order_by(TrafficMetricAssignment.assignee_id, TrafficMetric.name)
        ).all()
        grouped: dict[int, list[tuple[int, str]]] = {}
        for assignee_id, metric_id, metric_name in rows:
            grouped.setdefault(assignee_id, []).append((metric_id, metric_name))
        users = {
            user.id: user
            for user in _users_with_feature(db, FEATURE_TRAFFIC)
            if user.id in grouped
        }
        for user_id, missing in grouped.items():
            user = users.get(user_id)
            if user is None:
                continue
            names = [name for _, name in missing]
            summary = "、".join(names[:5])
            if len(names) > 5:
                summary += f" 等 {len(names)} 项"
            notification = NotificationService(db).notify(
                recipient=user,
                notification_type="traffic.weekly_metric_missing",
                title="上周红绿灯指标尚未填写",
                body=f"上周（{week_start.isoformat()}）有 {len(names)} 项周指标未填写：{summary}。",
                action_url="/traffic-light?tab=pending",
                dedupe_key=f"traffic.weekly_metric_missing:{user.id}:{week_start.isoformat()}",
                metadata={
                    "week_start": week_start.isoformat(),
                    "metric_ids": [metric_id for metric_id, _ in missing],
                },
            )
            if notification is not None and notification.id is None:
                created += 1
        db.commit()
        return created
    except Exception:
        db.rollback()
        logger.exception("weekly metric missing notification scan failed")
        return 0
    finally:
        db.close()


def run_daily_1700_notifications() -> None:
    """Run the evening missing-report reminder independently from AI scoring."""
    notify_missing_daily_reports(slot="1700")


def start_scheduler() -> BackgroundScheduler | None:
    global _scheduler, _scheduler_lock
    if _scheduler is not None:
        return _scheduler
    _scheduler_lock = _acquire_scheduler_lock()
    if _scheduler_lock is None:
        logger.info("scheduler not started; another process owns the scheduler lock")
        return None
    scheduler = BackgroundScheduler(timezone=settings.tz)
    scheduler.add_job(
        materialize_recurring_daily_tasks,
        "cron", hour=0, minute=5, id="materialize_recurring_tasks", replace_existing=True,
    )
    scheduler.add_job(
        lambda: notify_missing_daily_reports(slot="1000"),
        "cron", hour=10, minute=0, id="daily_missing_morning", replace_existing=True,
    )
    scheduler.add_job(
        run_daily_1700_notifications,
        "cron", hour=17, minute=0, id="daily_missing_evening", replace_existing=True,
    )
    scheduler.add_job(
        generate_daily_scores_for_all_active_users,
        "cron", hour=17, minute=30, id="daily_score_evening", replace_existing=True,
    )
    scheduler.add_job(
        notify_missing_weekly_metrics,
        "cron", day_of_week="mon", hour=10, minute=5,
        id="traffic_weekly_metric_missing", replace_existing=True,
    )
    scheduler.add_job(
        deliver_pending_feishu_notifications,
        "interval", minutes=1, id="feishu_notification_delivery", replace_existing=True,
    )
    scheduler.add_job(
        generate_daily_suggestions_for_all_active_users,
        "cron", hour=7, minute=50, id="daily_suggestions_morning", replace_existing=True,
    )
    scheduler.add_job(
        generate_daily_scores_for_all_active_users,
        "cron", hour=23, minute=30, id="daily_score_final", replace_existing=True,
    )
    scheduler.add_job(
        generate_weekly_scores_for_all_active_users,
        "cron", day_of_week="mon", hour=0, minute=10, id="weekly_score", replace_existing=True,
    )
    scheduler.add_job(
        generate_okr_reviews_for_all_active_users,
        "cron", day="last", hour=23, minute=30, id="okr_review_monthly", replace_existing=True,
    )
    scheduler.add_job(
        generate_monthly_report_scores_for_all_active_users,
        "cron", day="last", hour=23, minute=40, id="monthly_report_score", replace_existing=True,
    )
    scheduler.add_job(
        cleanup_stale_ai_tasks,
        "cron", hour=3, minute=0, id="cleanup_ai_tasks", replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler
    logger.info("AI scheduler started (tz=%s)", settings.tz)
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
    _release_scheduler_lock()
