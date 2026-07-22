"""Single-instance APScheduler jobs (design doc §12).

The recurring-task job always runs. AI jobs run in worker threads, are gated by
feature flags, and skip silently when the provider is unconfigured.
"""

from __future__ import annotations

import logging
import os
from datetime import timedelta
from pathlib import Path
from typing import BinaryIO

from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy import select

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.ai import AiFeatureFlags, AiTask
from app.models.user import User
from app.services.ai.provider import AiProviderError
from app.services.ai_service import AiService
from app.services.daily_service import materialize_recurring_tasks
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
        generate_daily_scores_for_all_active_users,
        "cron", hour=17, minute=0, id="daily_score_initial", replace_existing=True,
    )
    scheduler.add_job(
        generate_daily_suggestions_for_all_active_users,
        "cron", hour=7, minute=50, id="daily_suggestions_morning", replace_existing=True,
    )
    scheduler.add_job(
        generate_daily_scores_for_all_active_users,
        "cron", hour=23, minute=50, id="daily_score_final", replace_existing=True,
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
