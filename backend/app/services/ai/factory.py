from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ai import AiProviderConfig
from app.services.ai.openai_compatible import (
    DEFAULT_BASES,
    INTERFACE_OPENAI_CHAT,
    make_provider,
)
from app.services.ai.provider import AiProvider, AiProviderError, AiProviderNotConfigured
from app.utils.crypto import decrypt_secret


def get_provider_config(db: Session) -> AiProviderConfig | None:
    return db.scalar(
        select(AiProviderConfig).where(
            AiProviderConfig.id == 1,
            AiProviderConfig.deleted_at.is_(None),
        )
    )


def build_provider(db: Session) -> tuple[AiProvider, str]:
    """Build a provider from the stored config. Returns (provider, default_model).

    Raises AiProviderError when unconfigured/disabled so callers can render a
    friendly empty state instead of a hard failure.
    """
    cfg = get_provider_config(db)
    if cfg is None or not cfg.enabled:
        raise AiProviderNotConfigured("AI provider is not enabled")

    api_key = decrypt_secret(cfg.api_key_encrypted)
    if not api_key:
        raise AiProviderNotConfigured("AI provider api_key is not configured")

    interface_type = cfg.provider or INTERFACE_OPENAI_CHAT
    api_base = cfg.api_base or DEFAULT_BASES.get(interface_type, "")
    if not cfg.default_model:
        raise AiProviderNotConfigured("AI provider default_model is not configured")

    provider = make_provider(interface_type, api_base=api_base, api_key=api_key)
    return provider, cfg.default_model
