from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.tz))


def local_today() -> date:
    return local_now().date()
