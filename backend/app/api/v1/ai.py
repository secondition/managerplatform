from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_user
from app.db.session import get_db
from app.models.ai import AiTask
from app.models.user import User
from app.schemas.ai import AiFeatureFlagsOut, AiTaskOut
from app.services.ai_service import AiService

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/features", response_model=AiFeatureFlagsOut)
def get_features(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AiFeatureFlagsOut:
    """User-facing read of the AI feature toggles so the daily/OKR pages can hide
    panels for disabled features. Writing stays under admin:ai."""
    return AiService(db, user).get_flags()


@router.get("/tasks", response_model=list[AiTaskOut])
def list_tasks(
    limit: int = Query(default=20, le=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[AiTask]:
    return list(
        db.scalars(
            select(AiTask)
            .where(AiTask.user_id == user.id, AiTask.deleted_at.is_(None))
            .order_by(AiTask.id.desc())
            .limit(limit)
        ).all()
    )


@router.get("/tasks/{task_id}", response_model=AiTaskOut)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> AiTask:
    row = db.scalar(
        select(AiTask).where(
            AiTask.id == task_id,
            AiTask.user_id == user.id,
            AiTask.deleted_at.is_(None),
        )
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return row
