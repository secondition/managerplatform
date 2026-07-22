from fastapi import APIRouter, Depends

from app.api.v1 import (
    admin,
    admin_ai,
    ai,
    auth,
    daily,
    groups,
    okr,
    people,
    settings,
    subscriptions,
    traffic,
    users,
)
from app.api.v1.deps import require_permission
from app.core.permissions import FEATURE_DAILY, FEATURE_OKR, FEATURE_TRAFFIC

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
# Feature gates apply by permission row for every user, including owner.
api_router.include_router(daily.router, dependencies=[Depends(require_permission(FEATURE_DAILY))])
api_router.include_router(traffic.router, dependencies=[Depends(require_permission(FEATURE_TRAFFIC))])
api_router.include_router(okr.router, dependencies=[Depends(require_permission(FEATURE_OKR))])
api_router.include_router(users.router)
api_router.include_router(admin.router)
api_router.include_router(admin_ai.router)
api_router.include_router(ai.router)
api_router.include_router(groups.router)
api_router.include_router(subscriptions.router)
api_router.include_router(people.router)
api_router.include_router(settings.router)
