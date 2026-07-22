from datetime import date, datetime

from app.schemas.common import ORMModel


class PersonUserOut(ORMModel):
    id: int
    name: str
    email: str | None
    avatar_url: str | None
    profile_signature: str | None
    role: str
    department_id: int | None
    department_name: str | None = None
    status: str
    last_login_at: datetime | None
    last_synced_at: datetime | None


class PersonSubscriptionOut(ORMModel):
    subscribed: bool
    daily_enabled: bool
    okr_enabled: bool


class PersonSocialOut(ORMModel):
    followers_count: int
    following_count: int


class PersonAiScoreOut(ORMModel):
    status: str
    score: int | None = None
    summary: str | None = None
    updated_at: datetime | None = None


class PersonCalendarDayOut(ORMModel):
    date: date
    is_workday: bool
    is_future: bool
    has_daily: bool
    state: str


class PersonMonthlyDailyOut(ORMModel):
    month: str
    done_days: int
    missing_days: int
    required_days: int
    task_completion_rate: float | None
    completed_tasks: int
    total_tasks: int
    days: list[PersonCalendarDayOut]


class PersonProfileOut(ORMModel):
    user: PersonUserOut
    is_self: bool
    subscription: PersonSubscriptionOut
    social: PersonSocialOut
    daily_score: PersonAiScoreOut
    okr_review: PersonAiScoreOut
    daily_calendar: PersonMonthlyDailyOut


class PersonSignatureUpdate(ORMModel):
    profile_signature: str | None = None
