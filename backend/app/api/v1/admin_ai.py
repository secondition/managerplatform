from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, require_permission
from app.core.permissions import ADMIN_AI
from app.db.session import get_db
from app.models.user import User
from app.schemas.ai import (
    AiFeatureFlagsOut,
    AiFeatureFlagsUpdate,
    AiProviderOut,
    AiProviderTestOut,
    AiProviderUpdate,
    PromptConfigOut,
    PromptConfigUpdate,
)
from app.services.admin_ai_service import AdminAiService
from app.services.ai.provider import AiProviderError

router = APIRouter(prefix="/admin/ai", tags=["admin-ai"])


def _serialize_prompt(service: AdminAiService, row) -> PromptConfigOut:
    return PromptConfigOut(
        id=row.id,
        prompt_type=row.prompt_type,
        name=row.name,
        template_content=row.template_content,
        version=row.version,
        variables=row.variables_json or [],
        available_variables=service.available_variables_for(row.prompt_type),
    )


# ---- provider ----


@router.get("/provider", response_model=AiProviderOut)
def get_provider(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AI)),
) -> AiProviderOut:
    service = AdminAiService(db, user)
    return service.serialize_provider(service.get_provider())


@router.patch("/provider", response_model=AiProviderOut, dependencies=[Depends(csrf_protect)])
def update_provider(
    payload: AiProviderUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AI)),
) -> AiProviderOut:
    service = AdminAiService(db, user)
    return service.serialize_provider(service.update_provider(payload))


@router.post("/provider/test", response_model=AiProviderTestOut, dependencies=[Depends(csrf_protect)])
def test_provider(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AI)),
) -> AiProviderTestOut:
    return AdminAiService(db, user).test_provider()


# ---- feature flags ----


@router.get("/features", response_model=AiFeatureFlagsOut)
def get_features(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AI)),
) -> AiFeatureFlagsOut:
    return AiFeatureFlagsOut.model_validate(AdminAiService(db, user).get_flags())


@router.patch("/features", response_model=AiFeatureFlagsOut, dependencies=[Depends(csrf_protect)])
def update_features(
    payload: AiFeatureFlagsUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AI)),
) -> AiFeatureFlagsOut:
    return AiFeatureFlagsOut.model_validate(AdminAiService(db, user).update_flags(payload))


# ---- prompts ----


@router.get("/prompts", response_model=list[PromptConfigOut])
def list_prompts(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AI)),
) -> list[PromptConfigOut]:
    service = AdminAiService(db, user)
    return [_serialize_prompt(service, row) for row in service.list_prompts()]


@router.patch(
    "/prompts/{prompt_type}", response_model=PromptConfigOut, dependencies=[Depends(csrf_protect)]
)
def update_prompt(
    prompt_type: str,
    payload: PromptConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AI)),
) -> PromptConfigOut:
    service = AdminAiService(db, user)
    try:
        row = service.update_prompt(prompt_type, payload)
    except AiProviderError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize_prompt(service, row)


@router.post(
    "/prompts/{prompt_type}/restore-default",
    response_model=PromptConfigOut,
    dependencies=[Depends(csrf_protect)],
)
def restore_prompt_default(
    prompt_type: str,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AI)),
) -> PromptConfigOut:
    service = AdminAiService(db, user)
    try:
        row = service.restore_prompt_default(prompt_type)
    except AiProviderError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return _serialize_prompt(service, row)
