from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import utcnow
from app.models.user import RefreshToken


def revoke_user_refresh_tokens(db: Session, user_id: int, updated_by: int | None) -> None:
    now = utcnow()
    rows = db.scalars(
        select(RefreshToken).where(
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.deleted_at.is_(None),
        )
    ).all()
    for row in rows:
        row.revoked_at = now
        row.updated_by = updated_by
