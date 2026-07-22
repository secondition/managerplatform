from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, get_current_user, get_user_permissions
from app.core.permissions import FEATURE_DAILY, FEATURE_OKR
from app.db.session import get_db
from app.models.user import User
from app.schemas.people import PersonProfileOut, PersonSignatureUpdate, PersonSubscriptionOut
from app.services.people_service import PeopleService
from app.utils.time import local_today

router = APIRouter(prefix="/people", tags=["people"])


def _default_month() -> str:
    today = local_today()
    return f"{today.year:04d}-{today.month:02d}"


@router.get("/me", response_model=PersonProfileOut)
def get_my_profile(
    month: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PersonProfileOut:
    return PeopleService(db, user).get_profile(user.id, month or _default_month())


@router.patch(
    "/me/signature",
    response_model=PersonProfileOut,
    dependencies=[Depends(csrf_protect)],
)
def update_my_signature(
    payload: PersonSignatureUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PersonProfileOut:
    return PeopleService(db, user).update_my_signature(payload)


@router.post(
    "/me/avatar",
    response_model=PersonProfileOut,
    dependencies=[Depends(csrf_protect)],
)
async def upload_my_avatar(
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PersonProfileOut:
    return await PeopleService(db, user).upload_my_avatar(avatar)


@router.get("/{user_id}", response_model=PersonProfileOut)
def get_person_profile(
    user_id: int,
    month: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PersonProfileOut:
    return PeopleService(db, user).get_profile(user_id, month or _default_month())


@router.post(
    "/{user_id}/subscribe",
    response_model=PersonSubscriptionOut,
    dependencies=[Depends(csrf_protect)],
)
def subscribe_person(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> PersonSubscriptionOut:
    permissions = set(get_user_permissions(user, db))
    daily_enabled = FEATURE_DAILY in permissions
    okr_enabled = FEATURE_OKR in permissions
    if not daily_enabled and not okr_enabled:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No subscribable feature enabled")
    return PeopleService(db, user).subscribe_person(
        user_id,
        daily_enabled=daily_enabled,
        okr_enabled=okr_enabled,
    )


@router.delete(
    "/{user_id}/subscribe",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(csrf_protect)],
)
def unsubscribe_person(
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    PeopleService(db, user).unsubscribe_person(user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
