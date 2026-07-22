from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AiFeatureFlags, AiProviderConfig, PromptConfig
from app.models.user import User
from app.schemas.ai import (
    AiFeatureFlagsUpdate,
    AiProviderOut,
    AiProviderTestOut,
    AiProviderUpdate,
    PromptConfigUpdate,
)
from app.services.ai.defaults import (
    AVAILABLE_VARIABLES,
    DEFAULT_NAMES,
    DEFAULT_TEMPLATES,
    DEFAULT_VARIABLES,
    PROMPT_TYPES,
)
from app.services.ai.openai_compatible import DEFAULT_BASES, INTERFACE_OPENAI_CHAT, make_provider
from app.services.ai.provider import AiProviderError
from app.services.ai_service import AiService
from app.utils.crypto import decrypt_secret, encrypt_secret, mask_secret


class AdminAiService:
    def __init__(self, db: Session, actor: User) -> None:
        self.db = db
        self.actor = actor

    # ---- provider ----------------------------------------------------

    def get_provider(self) -> AiProviderConfig:
        row = self.db.scalar(
            select(AiProviderConfig).where(
                AiProviderConfig.id == 1, AiProviderConfig.deleted_at.is_(None)
            )
        )
        if row is None:
            row = AiProviderConfig(id=1, created_by=self.actor.id, updated_by=self.actor.id)
            self.db.add(row)
            self.db.commit()
            self.db.refresh(row)
        return row

    def serialize_provider(self, row: AiProviderConfig) -> AiProviderOut:
        key = decrypt_secret(row.api_key_encrypted)
        return AiProviderOut(
            provider=row.provider,
            api_base=row.api_base,
            default_model=row.default_model,
            enabled=row.enabled,
            api_key_masked=mask_secret(key),
            api_key_set=bool(key),
        )

    def update_provider(self, payload: AiProviderUpdate) -> AiProviderConfig:
        row = self.get_provider()
        if payload.provider is not None:
            row.provider = payload.provider.strip()
        if payload.api_base is not None:
            row.api_base = payload.api_base.strip()
        if payload.default_model is not None:
            row.default_model = payload.default_model.strip()
        if payload.enabled is not None:
            row.enabled = payload.enabled
        # api_key: None = keep, "" = clear, otherwise replace.
        if payload.api_key is not None:
            row.api_key_encrypted = (
                encrypt_secret(payload.api_key) if payload.api_key.strip() else None
            )
        row.updated_by = self.actor.id
        self.db.commit()
        self.db.refresh(row)
        return row

    def test_provider(self) -> AiProviderTestOut:
        row = self.get_provider()
        key = decrypt_secret(row.api_key_encrypted)
        if not key:
            return AiProviderTestOut(ok=False, message="未配置 API Key")
        if not row.default_model:
            return AiProviderTestOut(ok=False, message="未配置默认模型")
        interface_type = row.provider or INTERFACE_OPENAI_CHAT
        api_base = row.api_base or DEFAULT_BASES.get(interface_type, "")
        try:
            provider = make_provider(interface_type, api_base=api_base, api_key=key)
            resp = asyncio.run(
                provider.chat(
                    row.default_model,
                    [{"role": "user", "content": "ping，请回复 pong"}],
                    max_tokens=10,
                )
            )
        except AiProviderError as exc:
            return AiProviderTestOut(ok=False, message=str(exc)[:300])
        return AiProviderTestOut(ok=True, message=f"连通成功（模型 {resp.model}）")

    # ---- feature flags -----------------------------------------------

    def get_flags(self) -> AiFeatureFlags:
        return AiService(self.db, self.actor).get_flags()

    def update_flags(self, payload: AiFeatureFlagsUpdate) -> AiFeatureFlags:
        row = self.get_flags()
        data = payload.model_dump(exclude_unset=True)
        for field, value in data.items():
            setattr(row, field, value)
        row.updated_by = self.actor.id
        self.db.commit()
        self.db.refresh(row)
        return row

    # ---- prompts -----------------------------------------------------

    def list_prompts(self) -> list[PromptConfig]:
        service = AiService(self.db, self.actor)
        return [service.get_prompt(pt) for pt in PROMPT_TYPES]

    def available_variables_for(self, prompt_type: str) -> list[dict]:
        return AVAILABLE_VARIABLES.get(prompt_type, [])

    def _get_prompt_or_404(self, prompt_type: str) -> PromptConfig:
        if prompt_type not in PROMPT_TYPES:
            raise AiProviderError("unknown prompt type")
        return AiService(self.db, self.actor).get_prompt(prompt_type)

    def update_prompt(self, prompt_type: str, payload: PromptConfigUpdate) -> PromptConfig:
        row = self._get_prompt_or_404(prompt_type)
        if payload.name is not None:
            row.name = payload.name.strip()
        if payload.template_content is not None:
            row.template_content = payload.template_content
        if payload.version is not None:
            row.version = payload.version.strip() or row.version
        if payload.variables is not None:
            # Keep only keys that exist in this prompt type's catalog, preserving order.
            valid = {v["key"] for v in AVAILABLE_VARIABLES.get(prompt_type, [])}
            row.variables_json = [k for k in payload.variables if k in valid]
        row.updated_by = self.actor.id
        self.db.commit()
        self.db.refresh(row)
        return row

    def restore_prompt_default(self, prompt_type: str) -> PromptConfig:
        row = self._get_prompt_or_404(prompt_type)
        row.template_content = DEFAULT_TEMPLATES.get(prompt_type, "")
        row.name = DEFAULT_NAMES.get(prompt_type, prompt_type)
        row.version = "v1"
        row.variables_json = list(DEFAULT_VARIABLES.get(prompt_type, []))
        row.updated_by = self.actor.id
        self.db.commit()
        self.db.refresh(row)
        return row
