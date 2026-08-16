from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.deps import csrf_protect, require_permission
from app.core.chat_sync_worker import wake_chat_sync_worker
from app.core.permissions import ADMIN_AGENT
from app.db.session import get_db
from app.models.user import User
from app.schemas.agent import (
    AgentAccessOut,
    AgentAccessUpdate,
    AgentFeishuChatConfigOut,
    AgentFeishuChatConfigUpdate,
    AgentPresentationUpdate,
    AdminAgentOut,
)
from app.services.agent_chat_config import AgentChatConfig
from app.services.agent_access_service import AgentAccessService

router = APIRouter(prefix="/admin/agents", tags=["admin-agents"])


@router.get("", response_model=list[AdminAgentOut])
def list_agents(
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AGENT)),
) -> list[dict]:
    del user
    return AgentAccessService(db).list_admin_agents()


@router.patch(
    "/{agent_id}",
    response_model=AdminAgentOut,
    dependencies=[Depends(csrf_protect)],
)
def update_agent_presentation(
    agent_id: int,
    payload: AgentPresentationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AGENT)),
) -> dict:
    return AgentAccessService(db).update_agent_presentation(
        agent_id,
        name=payload.name,
        description=payload.description,
        actor=user,
    )


@router.post(
    "/{agent_id}/avatar",
    response_model=AdminAgentOut,
    dependencies=[Depends(csrf_protect)],
)
async def upload_agent_avatar(
    agent_id: int,
    avatar: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AGENT)),
) -> dict:
    return await AgentAccessService(db).upload_agent_avatar(
        agent_id,
        file=avatar,
        actor=user,
    )


@router.delete(
    "/{agent_id}/avatar",
    response_model=AdminAgentOut,
    dependencies=[Depends(csrf_protect)],
)
def remove_agent_avatar(
    agent_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AGENT)),
) -> dict:
    return AgentAccessService(db).remove_agent_avatar(agent_id, actor=user)


@router.get(
    "/{agent_id}/feishu-chat-config",
    response_model=AgentFeishuChatConfigOut,
)
def get_agent_feishu_chat_config(
    agent_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AGENT)),
) -> dict:
    del user
    return AgentAccessService(db).get_agent_feishu_chat_config(agent_id)


@router.patch(
    "/{agent_id}/feishu-chat-config",
    response_model=AgentFeishuChatConfigOut,
    dependencies=[Depends(csrf_protect)],
)
def update_agent_feishu_chat_config(
    agent_id: int,
    payload: AgentFeishuChatConfigUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AGENT)),
) -> dict:
    return AgentAccessService(db).update_agent_feishu_chat_config(
        agent_id,
        config=AgentChatConfig(
            target_chat_id=payload.target_chat_id,
            target_chat_name=payload.target_chat_name,
            agent_sender_id=payload.agent_sender_id,
            agent_mention_id=payload.agent_mention_id,
            agent_display_name=payload.agent_display_name,
        ),
        actor=user,
    )


@router.get("/{agent_id}/access", response_model=AgentAccessOut)
def get_agent_access(
    agent_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AGENT)),
) -> dict:
    del user
    service = AgentAccessService(db)
    return service.serialize_agent_access(service.get_agent_by_id(agent_id))


@router.put(
    "/{agent_id}/access",
    response_model=AgentAccessOut,
    dependencies=[Depends(csrf_protect)],
)
async def replace_agent_access(
    agent_id: int,
    payload: AgentAccessUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_permission(ADMIN_AGENT)),
) -> dict:
    result = AgentAccessService(db).replace_agent_access(
        agent_id,
        user_ids=payload.user_ids,
        group_ids=payload.group_ids,
        actor=user,
    )
    wake_chat_sync_worker()
    return result
