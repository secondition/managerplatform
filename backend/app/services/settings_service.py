from __future__ import annotations

import secrets
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models.org import CompanySetting
from app.models.user import User
from app.schemas.admin import CompanySettingUpdate
from app.utils.image_upload import delete_managed_upload, validate_raster_image

DEFAULT_COMPANY_NAME = "企业工作管理平台"
DEFAULT_FOOTER_TEXT = "WORK MANAGEMENT DESK · 企业工作管理平台 MVP"
UPLOAD_DIR = Path(__file__).resolve().parents[2] / "storage" / "uploads" / "logos"
MAX_LOGO_BYTES = 2 * 1024 * 1024


class SettingsService:
    def __init__(self, db: Session, actor: User | None = None) -> None:
        self.db = db
        self.actor = actor

    def get_company_setting(self) -> CompanySetting:
        row = self.db.scalar(
            select(CompanySetting).where(
                CompanySetting.id == 1,
                CompanySetting.deleted_at.is_(None),
            )
        )
        if row is not None:
            return row
        row = CompanySetting(
            id=1,
            company_name=DEFAULT_COMPANY_NAME,
            footer_text=DEFAULT_FOOTER_TEXT,
            created_by=self.actor.id if self.actor else None,
            updated_by=self.actor.id if self.actor else None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def update_company_setting(self, payload: CompanySettingUpdate) -> CompanySetting:
        row = self.get_company_setting()
        row.company_name = payload.company_name.strip()
        row.footer_text = payload.footer_text.strip()
        row.updated_by = self.actor.id if self.actor else None
        self.db.commit()
        self.db.refresh(row)
        return row

    async def upload_logo(self, file: UploadFile) -> CompanySetting:
        content = await file.read(MAX_LOGO_BYTES + 1)
        if len(content) > MAX_LOGO_BYTES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Logo file is too large")
        try:
            suffix = validate_raster_image(
                content,
                filename=file.filename,
                content_type=file.content_type,
            )
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        filename = f"company-logo-{utcnow().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(4)}{suffix}"
        path = UPLOAD_DIR / filename
        path.write_bytes(content)

        row = self.get_company_setting()
        previous_url = row.logo_url
        row.logo_url = f"/uploads/logos/{filename}"
        row.updated_by = self.actor.id if self.actor else None
        try:
            self.db.commit()
        except Exception:
            path.unlink(missing_ok=True)
            raise
        self.db.refresh(row)
        delete_managed_upload(previous_url, "/uploads/logos/", UPLOAD_DIR)
        return row
