from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, get_current_user, require_permission
from app.core.permissions import ADMIN_SETTINGS
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import CompanySettingOut, CompanySettingUpdate
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/public", response_model=CompanySettingOut)
def get_public_company_settings(db: Session = Depends(get_db)) -> CompanySettingOut:
    return SettingsService(db).get_company_setting()


@router.get("/company", response_model=CompanySettingOut)
def get_company_settings(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_SETTINGS)),
) -> CompanySettingOut:
    return SettingsService(db, user).get_company_setting()


@router.patch(
    "/company",
    response_model=CompanySettingOut,
    dependencies=[Depends(csrf_protect)],
)
def update_company_settings(
    payload: CompanySettingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_SETTINGS)),
) -> CompanySettingOut:
    return SettingsService(db, user).update_company_setting(payload)


@router.post(
    "/company/logo",
    response_model=CompanySettingOut,
    dependencies=[Depends(csrf_protect)],
)
async def upload_company_logo(
    logo: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_SETTINGS)),
) -> CompanySettingOut:
    return await SettingsService(db, user).upload_logo(logo)
