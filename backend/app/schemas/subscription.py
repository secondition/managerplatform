from datetime import datetime

from app.schemas.common import ORMModel
from app.schemas.daily import DailyReportOut
from app.schemas.okr import OkrMonthOut
from app.schemas.user import UserBrief


class DailySubscriptionOut(ORMModel):
    id: int
    target_user: UserBrief
    daily_enabled: bool
    okr_enabled: bool
    created_at: datetime


class DailySubscriptionCandidateOut(ORMModel):
    user: UserBrief
    subscribed: bool


class SubscribedDailyReportOut(DailyReportOut):
    target_user: UserBrief


class OkrSubscriptionOut(ORMModel):
    id: int
    target_user: UserBrief
    daily_enabled: bool
    okr_enabled: bool
    created_at: datetime


class OkrSubscriptionCandidateOut(ORMModel):
    user: UserBrief
    subscribed: bool


class SubscribedOkrMonthOut(OkrMonthOut):
    target_user: UserBrief
