from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


class AiProviderError(Exception):
    """Raised when the AI provider is unconfigured, disabled, or a call fails.

    Callers catch this and surface a friendly "not enabled" / error state rather
    than a 500 — AI is optional, the rest of the app must keep working.
    """


class AiProviderNotConfigured(AiProviderError):
    """Raised when generation is disabled or required provider settings are missing."""


@dataclass
class AiResponse:
    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    raw: dict = field(default_factory=dict)


class AiProvider(Protocol):
    async def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> AiResponse:
        ...
