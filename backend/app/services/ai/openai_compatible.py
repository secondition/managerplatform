from __future__ import annotations

import httpx

from app.services.ai.provider import AiProviderError, AiResponse

# Interface types the admin can pick. The DB column is still named ``provider``
# (no migration), but it now holds an *interface* value, not a vendor name.
INTERFACE_OPENAI_CHAT = "openai_chat"
INTERFACE_OPENAI_RESPONSE = "openai_response"
INTERFACE_ANTHROPIC = "anthropic"

# Default base URLs per interface; overridable via ai_provider_configs.api_base.
# Legacy keys (openai_compatible/deepseek/openai) included so old configs with a
# blank api_base still resolve. DeepSeek keeps its own base for convenience.
DEFAULT_BASES = {
    INTERFACE_OPENAI_CHAT: "https://api.openai.com",
    INTERFACE_OPENAI_RESPONSE: "https://api.openai.com",
    INTERFACE_ANTHROPIC: "https://api.anthropic.com",
    "openai_compatible": "https://api.openai.com",
    "openai": "https://api.openai.com",
    "deepseek": "https://api.deepseek.com",
}

ANTHROPIC_VERSION = "2023-06-01"


def _split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """Anthropic takes ``system`` as a top-level field, not a message role."""
    system_parts = [m["content"] for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    return "\n".join(system_parts), rest


class _BaseHttpProvider:
    def __init__(self, api_base: str, api_key: str, timeout: float = 60.0) -> None:
        if not api_base:
            raise AiProviderError("AI provider api_base is not configured")
        if not api_key:
            raise AiProviderError("AI provider api_key is not configured")
        self.api_base = api_base.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def _post(self, url: str, payload: dict, headers: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise AiProviderError(f"AI request failed: {exc}") from exc
        if resp.status_code >= 400:
            raise AiProviderError(f"AI provider returned {resp.status_code}: {resp.text[:300]}")
        try:
            return resp.json()
        except ValueError as exc:
            raise AiProviderError(f"AI response parse error: {exc}") from exc


class OpenAIChatProvider(_BaseHttpProvider):
    """OpenAI-compatible Chat Completions (``/v1/chat/completions``).

    Covers OpenAI, DeepSeek and most domestic OpenAI-compatible models.
    """

    async def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> AiResponse:
        payload: dict = {"model": model, "messages": messages, "temperature": temperature}
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = await self._post(f"{self.api_base}/v1/chat/completions", payload, headers)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise AiProviderError(f"AI response parse error: {exc}") from exc
        usage = data.get("usage") or {}
        return AiResponse(
            content=content,
            model=data.get("model", model),
            input_tokens=int(usage.get("prompt_tokens", 0) or 0),
            output_tokens=int(usage.get("completion_tokens", 0) or 0),
            raw=data,
        )


class OpenAIResponseProvider(_BaseHttpProvider):
    """OpenAI Responses API (``/v1/responses``)."""

    async def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> AiResponse:
        payload: dict = {
            "model": model,
            # Responses API accepts the same message shape under ``input``.
            "input": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            payload["max_output_tokens"] = max_tokens
        if json_mode:
            payload["text"] = {"format": {"type": "json_object"}}
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        data = await self._post(f"{self.api_base}/v1/responses", payload, headers)
        content = self._extract_output_text(data)
        if content is None:
            raise AiProviderError("AI response parse error: no output text")
        usage = data.get("usage") or {}
        return AiResponse(
            content=content,
            model=data.get("model", model),
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            raw=data,
        )

    @staticmethod
    def _extract_output_text(data: dict) -> str | None:
        # Convenience field first, then walk the structured output.
        if isinstance(data.get("output_text"), str):
            return data["output_text"]
        parts: list[str] = []
        for item in data.get("output") or []:
            for block in item.get("content") or []:
                text = block.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts) if parts else None


class AnthropicProvider(_BaseHttpProvider):
    """Anthropic Messages API (``/v1/messages``)."""

    async def chat(
        self,
        model: str,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        max_tokens: int | None = None,
        json_mode: bool = False,
    ) -> AiResponse:
        system, rest = _split_system(messages)
        payload: dict = {
            "model": model,
            "messages": rest,
            "temperature": temperature,
            # Anthropic requires max_tokens; default when unset.
            "max_tokens": max_tokens or 1500,
        }
        if system:
            payload["system"] = system
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": ANTHROPIC_VERSION,
            "Content-Type": "application/json",
        }
        data = await self._post(f"{self.api_base}/v1/messages", payload, headers)
        try:
            blocks = data["content"]
            content = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise AiProviderError(f"AI response parse error: {exc}") from exc
        usage = data.get("usage") or {}
        return AiResponse(
            content=content,
            model=data.get("model", model),
            input_tokens=int(usage.get("input_tokens", 0) or 0),
            output_tokens=int(usage.get("output_tokens", 0) or 0),
            raw=data,
        )


_PROVIDERS = {
    INTERFACE_OPENAI_CHAT: OpenAIChatProvider,
    INTERFACE_OPENAI_RESPONSE: OpenAIResponseProvider,
    INTERFACE_ANTHROPIC: AnthropicProvider,
}

# Legacy interface values (stored before the openai_chat/response/anthropic
# split) map onto the current ones so old configs keep working.
_ALIASES = {
    "openai_compatible": INTERFACE_OPENAI_CHAT,
    "deepseek": INTERFACE_OPENAI_CHAT,
    "openai": INTERFACE_OPENAI_CHAT,
}


def make_provider(interface_type: str, api_base: str, api_key: str):
    resolved = _ALIASES.get(interface_type, interface_type)
    cls = _PROVIDERS.get(resolved)
    if cls is None:
        raise AiProviderError(f"unknown interface type: {interface_type}")
    return cls(api_base=api_base, api_key=api_key)
