from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import BinaryIO

from app.core.config import feishu_chat_runtime_summary, settings
from app.db.session import SessionLocal
from app.services.feishu_chat_sync_service import FeishuChatSyncService
from app.services.feishu_tenant_client import FeishuTenantClient, FeishuTenantError

logger = logging.getLogger("app.feishu_chat_sync")

_LOCK_PATH = Path(__file__).resolve().parents[2] / "storage" / "feishu_chat_sync.lock"
_worker_lock: BinaryIO | None = None
_worker_task: asyncio.Task[None] | None = None
_stop_event: asyncio.Event | None = None
_wake_event: asyncio.Event | None = None


def _acquire_worker_lock() -> BinaryIO | None:
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


def _release_worker_lock() -> None:
    global _worker_lock
    if _worker_lock is None:
        return
    try:
        _worker_lock.seek(0)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(_worker_lock.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(_worker_lock.fileno(), fcntl.LOCK_UN)
    finally:
        _worker_lock.close()
        _worker_lock = None


def start_chat_sync_worker() -> asyncio.Task[None] | None:
    global _worker_lock, _worker_task, _stop_event, _wake_event
    if not settings.feishu_chat_enabled:
        return None
    if _worker_task is not None and not _worker_task.done():
        return _worker_task
    _worker_lock = _acquire_worker_lock()
    if _worker_lock is None:
        logger.info("chat sync worker not started; another process owns the lock")
        return None
    _stop_event = asyncio.Event()
    _wake_event = asyncio.Event()
    _worker_task = asyncio.create_task(
        _run_worker(_stop_event),
        name="feishu-chat-sync",
    )
    logger.warning("Feishu chat sync worker started: %s", feishu_chat_runtime_summary())
    return _worker_task


def wake_chat_sync_worker() -> bool:
    if _worker_task is None or _worker_task.done() or _wake_event is None:
        return False
    _wake_event.set()
    return True


async def shutdown_chat_sync_worker() -> None:
    global _worker_task, _stop_event, _wake_event
    task = _worker_task
    if task is not None:
        if _stop_event is not None:
            _stop_event.set()
        if _wake_event is not None:
            _wake_event.set()
        try:
            await asyncio.wait_for(task, timeout=10.0)
        except asyncio.TimeoutError:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        _worker_task = None
        _stop_event = None
        _wake_event = None
    _release_worker_lock()


async def _run_worker(stop_event: asyncio.Event) -> None:
    client = FeishuTenantClient(settings)
    try:
        while not stop_event.is_set():
            db = SessionLocal()
            started_at = time.monotonic()
            try:
                result = await FeishuChatSyncService(
                    db,
                    tenant_client=client,
                ).sync_due()
                if result.message_pages or result.member_pages:
                    logger.info(
                        "chat sync completed status=%s message_pages=%s messages=%s "
                        "member_pages=%s members=%s duration_ms=%s",
                        result.status,
                        result.message_pages,
                        result.message_count,
                        result.member_pages,
                        result.member_count,
                        round((time.monotonic() - started_at) * 1000),
                    )
            except FeishuTenantError as exc:
                db.rollback()
                logger.warning(
                    "chat sync deferred category=%s retryable=%s rate_limited=%s log_id=%s",
                    exc.category,
                    exc.retryable,
                    exc.rate_limited,
                    exc.log_id or "<none>",
                )
            except asyncio.CancelledError:
                db.rollback()
                raise
            except Exception:
                db.rollback()
                logger.error("chat sync iteration failed category=internal_error")
            finally:
                db.close()

            wake_event = _wake_event
            if wake_event is None:
                continue
            try:
                await asyncio.wait_for(
                    wake_event.wait(),
                    timeout=max(
                        1,
                        min(settings.feishu_chat_sync_interval_seconds, 5),
                    ),
                )
            except asyncio.TimeoutError:
                pass
            finally:
                wake_event.clear()
    finally:
        await client.aclose()
