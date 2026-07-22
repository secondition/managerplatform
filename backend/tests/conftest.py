from __future__ import annotations

from datetime import date, time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — register all tables on Base.metadata
from app.db.base import Base
from app.models.daily import DailyReport, DailyTask
from app.models.okr import OkrObjective
from app.models.user import User


@pytest.fixture()
def db():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture()
def user(db):
    u = User(
        name="Tester",
        role="member",
        feishu_union_id="u-1",
        feishu_open_id="o-1",
        status="active",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture()
def daily_report(db, user):
    report = DailyReport(user_id=user.id, report_date=date(2026, 7, 10), status="draft")
    db.add(report)
    db.flush()
    db.add(
        DailyTask(
            report_id=report.id,
            user_id=user.id,
            task_time=time(9, 30),
            content="整理销售数据",
        )
    )
    db.commit()
    return report


@pytest.fixture()
def objective(db, user):
    obj = OkrObjective(user_id=user.id, month="2026-07", title="提升指标A")
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
