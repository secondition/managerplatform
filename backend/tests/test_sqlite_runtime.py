from __future__ import annotations

import sqlite3

from app.core.config import BACKEND_DIR, Settings
from app.core import scheduler
from app.db.session import _enable_sqlite_foreign_keys


def test_relative_sqlite_path_is_resolved_from_backend_directory():
    settings = Settings(_env_file=None, database_url="sqlite:///./storage/example.db")

    expected = (BACKEND_DIR / "storage" / "example.db").resolve().as_posix()
    assert settings.database_url == f"sqlite:///{expected}"


def test_sqlite_connection_enables_wal_and_busy_wait(tmp_path):
    connection = sqlite3.connect(tmp_path / "runtime.db")
    try:
        _enable_sqlite_foreign_keys(connection, None)
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 30000
    finally:
        connection.close()


def test_scheduler_file_lock_allows_only_one_owner(tmp_path, monkeypatch):
    monkeypatch.setattr(scheduler, "_LOCK_PATH", tmp_path / "scheduler.lock")
    first = scheduler._acquire_scheduler_lock()
    assert first is not None
    try:
        assert scheduler._acquire_scheduler_lock() is None
    finally:
        scheduler._scheduler_lock = first
        scheduler._release_scheduler_lock()

    second = scheduler._acquire_scheduler_lock()
    assert second is not None
    scheduler._scheduler_lock = second
    scheduler._release_scheduler_lock()
