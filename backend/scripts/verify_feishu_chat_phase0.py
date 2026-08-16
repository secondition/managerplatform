from __future__ import annotations

import argparse
import html
import json
import re
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import (  # noqa: E402
    Settings,
    chat_target_fingerprint,
    feishu_chat_runtime_summary,
    validate_feishu_chat_settings,
)
from app.services.feishu_user_oauth_client import (  # noqa: E402
    CHAT_USER_OAUTH_SCOPES,
    REQUIRED_CHAT_SCOPES,
)

OAUTH_STATE_PATH = BACKEND_DIR / "storage" / "feishu_chat_phase0_oauth_state.json"


class Phase0VerificationError(RuntimeError):
    pass


class Phase0Client:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._tenant_token: str | None = None

    def tenant_access_token(self) -> str:
        if self._tenant_token:
            return self._tenant_token
        payload = self._request_json(
            "POST",
            self.settings.feishu_tenant_token_path,
            operation="获取应用身份令牌",
            json_body={
                "app_id": self.settings.feishu_app_id,
                "app_secret": self.settings.feishu_app_secret,
            },
        )
        token = payload.get("tenant_access_token") or _data_dict(payload).get(
            "tenant_access_token"
        )
        if not token:
            raise Phase0VerificationError("应用身份令牌响应缺少 tenant_access_token")
        self._tenant_token = str(token)
        return self._tenant_token

    def tenant_get(
        self,
        path: str,
        *,
        operation: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "GET",
            path,
            operation=operation,
            params=params,
            bearer_token=self.tenant_access_token(),
        )

    def user_post(
        self,
        path: str,
        *,
        operation: str,
        access_token: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._request_json(
            "POST",
            path,
            operation=operation,
            params=params,
            json_body=json_body,
            bearer_token=access_token,
        )

    def oauth_post(self, json_body: dict[str, Any], *, operation: str) -> dict[str, Any]:
        return self._request_json(
            "POST",
            self.settings.feishu_token_path,
            operation=operation,
            json_body=json_body,
        )

    def probe_tenant_resource(self, message_id: str, file_key: str) -> dict[str, Any]:
        url = (
            f"{self.settings.feishu_api_base.rstrip('/')}"
            f"/open-apis/im/v1/messages/{message_id}/resources/{file_key}"
        )
        headers = {"Authorization": f"Bearer {self.tenant_access_token()}"}
        try:
            with httpx.stream(
                "GET",
                url,
                params={"type": "file"},
                headers=headers,
                timeout=20.0,
            ) as response:
                if not response.is_success:
                    self._raise_response_error(response, "验证跨应用文件读取")
                first_chunk = next(response.iter_bytes(65_536), b"")
                return {
                    "ok": True,
                    "http_status": response.status_code,
                    "content_type": response.headers.get("content-type", "<unknown>"),
                    "sample_bytes": len(first_chunk),
                }
        except httpx.RequestError as exc:
            raise Phase0VerificationError(
                f"验证跨应用文件读取网络失败: {exc.__class__.__name__}"
            ) from exc

    def _request_json(
        self,
        method: str,
        path: str,
        *,
        operation: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        bearer_token: str | None = None,
    ) -> dict[str, Any]:
        url = f"{self.settings.feishu_api_base.rstrip('/')}{path}"
        headers = {"Authorization": f"Bearer {bearer_token}"} if bearer_token else None
        try:
            response = httpx.request(
                method,
                url,
                params=params,
                json=json_body,
                headers=headers,
                timeout=20.0,
            )
        except httpx.RequestError as exc:
            raise Phase0VerificationError(
                f"{operation}网络失败: {exc.__class__.__name__}"
            ) from exc
        if not response.is_success:
            self._raise_response_error(response, operation)
        try:
            payload = response.json()
        except ValueError as exc:
            raise Phase0VerificationError(
                f"{operation}返回非 JSON 响应 (HTTP {response.status_code})"
            ) from exc
        if not isinstance(payload, dict):
            raise Phase0VerificationError(f"{operation}返回结构异常")
        code = payload.get("code")
        if code not in (None, 0):
            raise Phase0VerificationError(_feishu_error_detail(payload, operation, response))
        return payload

    def _raise_response_error(self, response: httpx.Response, operation: str) -> None:
        try:
            payload = response.json()
        except ValueError:
            raise Phase0VerificationError(
                f"{operation}失败 (HTTP {response.status_code})"
            )
        if isinstance(payload, dict):
            raise Phase0VerificationError(_feishu_error_detail(payload, operation, response))
        raise Phase0VerificationError(f"{operation}失败 (HTTP {response.status_code})")


def command_discover(settings: Settings) -> dict[str, Any]:
    validate_feishu_chat_settings(settings, require_phase0=True)
    client = Phase0Client(settings)
    chats = _paged_items(
        client,
        "/open-apis/im/v1/chats",
        operation="获取应用 B 所在群列表",
        params={"page_size": 100},
    )
    results = []
    for chat in chats:
        chat_id = _string(chat.get("chat_id"))
        if not chat_id:
            continue
        results.append(
            {
                "name": _string(chat.get("name")) or "<unnamed>",
                "chat_id": chat_id,
                "fingerprint": chat_target_fingerprint(chat_id),
                "chat_status": _string(chat.get("chat_status")) or "<unknown>",
            }
        )
    return {
        "step": "discover",
        "runtime": feishu_chat_runtime_summary(settings),
        "chat_count": len(results),
        "chats": results,
    }


def command_readonly(
    settings: Settings,
    *,
    probe_file_resource: bool,
    message_pages: int = 1,
) -> dict[str, Any]:
    validate_feishu_chat_settings(settings, require_phase0=True, require_target=True)
    client = Phase0Client(settings)
    target = client.tenant_get(
        f"/open-apis/im/v1/chats/{settings.feishu_chat_target_chat_id}",
        operation="读取测试群信息",
    )
    chat = _data_dict(target)
    actual_name = _string(chat.get("name"))
    if actual_name != settings.feishu_chat_target_chat_name:
        raise Phase0VerificationError(
            "目标群名称与 FEISHU_CHAT_TARGET_CHAT_NAME 不一致，已停止验证"
        )

    members, members_error = _capture_paged_items(
        client,
        f"/open-apis/im/v1/chats/{settings.feishu_chat_target_chat_id}/members",
        operation="读取测试群成员",
        params={"page_size": 100, "member_id_type": "open_id"},
    )
    messages, messages_error = _capture_paged_items(
        client,
        "/open-apis/im/v1/messages",
        operation="读取测试群历史消息",
        params={
            "container_id_type": "chat",
            "container_id": settings.feishu_chat_target_chat_id,
            "sort_type": "ByCreateTimeDesc",
            "page_size": 50,
        },
        max_pages=max(1, min(message_pages, 20)),
    )
    analysis = _analyze_messages(messages, settings) if messages_error is None else None
    file_probe: dict[str, Any] = {"attempted": False}
    if probe_file_resource and messages_error is None:
        candidate = _find_agent_file_candidate(messages, settings.feishu_chat_agent_sender_id)
        if candidate is None:
            file_probe = {
                "attempted": False,
                "reason": "最近 50 条消息中没有找到可确认属于查宝的文件消息",
            }
        else:
            message_id, file_key = candidate
            file_probe = {
                "attempted": True,
                **client.probe_tenant_resource(message_id, file_key),
            }

    return {
        "step": "readonly",
        "runtime": feishu_chat_runtime_summary(settings),
        "target": {
            "name_matches": True,
            "fingerprint": settings.feishu_chat_target_fingerprint,
            "chat_status": _string(chat.get("chat_status")) or "<unknown>",
        },
        "members": {
            "ok": members_error is None,
            "error": members_error,
            "count": len(members),
            "requested_member_id_type": "open_id",
            "member_types": sorted(
                {
                    _string(item.get("member_type")) or "<unknown>"
                    for item in members
                }
            ),
            "has_member_ids": all(bool(_string(item.get("member_id"))) for item in members),
        },
        "messages": {
            "ok": messages_error is None,
            "error": messages_error,
            "analysis": analysis,
        },
        "file_resource_probe": file_probe,
    }


def command_oauth_url(settings: Settings) -> dict[str, Any]:
    validate_feishu_chat_settings(settings, require_phase0=True, require_target=True)
    state = secrets.token_urlsafe(32)
    OAUTH_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    OAUTH_STATE_PATH.write_text(
        json.dumps(
            {
                "state": state,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "target_fingerprint": settings.feishu_chat_target_fingerprint,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    query = urlencode(
        {
            "client_id": settings.feishu_app_id,
            "response_type": "code",
            "redirect_uri": settings.feishu_chat_oauth_redirect_uri,
            "scope": " ".join(CHAT_USER_OAUTH_SCOPES),
            "state": state,
        }
    )
    return {
        "step": "oauth_url",
        "target_fingerprint": settings.feishu_chat_target_fingerprint,
        "authorize_url": (
            f"{settings.feishu_authorize_base.rstrip('/')}"
            f"{settings.feishu_authorize_path}?{query}"
        ),
        "next": (
            "授权后将回调 URL 中的 code 和 state 分别放入进程环境变量 "
            "FEISHU_CHAT_PHASE0_AUTHORIZATION_CODE 与 FEISHU_CHAT_PHASE0_RETURNED_STATE，"
            "再运行 user-flow"
        ),
    }


def command_user_flow(
    settings: Settings,
    *,
    confirmation: str,
    wait_seconds: int,
) -> dict[str, Any]:
    validate_feishu_chat_settings(settings, require_phase0=True, require_target=True)
    expected_confirmation = f"TEST:{settings.feishu_chat_target_fingerprint}"
    if confirmation != expected_confirmation:
        raise Phase0VerificationError(
            f"发送确认值不匹配，应为 {expected_confirmation}"
        )
    if not settings.feishu_chat_agent_mention_id.strip():
        raise Phase0VerificationError("FEISHU_CHAT_AGENT_MENTION_ID 尚未配置")
    if not settings.feishu_chat_agent_sender_id.strip():
        raise Phase0VerificationError("FEISHU_CHAT_AGENT_SENDER_ID 尚未配置")

    code = _required_process_secret("FEISHU_CHAT_PHASE0_AUTHORIZATION_CODE")
    returned_state = _required_process_secret("FEISHU_CHAT_PHASE0_RETURNED_STATE")
    stored_state = _consume_oauth_state(settings)
    if not secrets.compare_digest(returned_state, stored_state):
        raise Phase0VerificationError("OAuth state 不匹配")

    client = Phase0Client(settings)
    mention_preflight = _preflight_user_flow_target(client, settings)
    token_payload = client.oauth_post(
        {
            "grant_type": "authorization_code",
            "client_id": settings.feishu_app_id,
            "client_secret": settings.feishu_app_secret,
            "code": code,
            "redirect_uri": settings.feishu_chat_oauth_redirect_uri,
        },
        operation="交换用户访问令牌",
    )
    access_token = _required_token_field(token_payload, "access_token")
    refresh_token = _required_token_field(token_payload, "refresh_token")
    granted_scopes = set(_scope_values(token_payload.get("scope")))
    missing_scopes = sorted(REQUIRED_CHAT_SCOPES - granted_scopes)
    if missing_scopes:
        raise Phase0VerificationError(
            f"实际用户授权缺少 scope: {', '.join(missing_scopes)}"
        )

    refreshed = client.oauth_post(
        {
            "grant_type": "refresh_token",
            "client_id": settings.feishu_app_id,
            "client_secret": settings.feishu_app_secret,
            "refresh_token": refresh_token,
        },
        operation="验证用户令牌刷新",
    )
    access_token = _required_token_field(refreshed, "access_token")
    _required_token_field(refreshed, "refresh_token")

    marker = f"MP-PHASE0-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
    text = _build_user_test_text(settings, marker)
    sent_payload = client.user_post(
        "/open-apis/im/v1/messages",
        operation="以当前用户身份发送测试消息",
        access_token=access_token,
        params={"receive_id_type": "chat_id"},
        json_body={
            "receive_id": settings.feishu_chat_target_chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
        },
    )
    sent_message_id = _string(_data_dict(sent_payload).get("message_id"))
    if not sent_message_id:
        raise Phase0VerificationError("发送响应缺少 message_id")

    replies: list[dict[str, Any]] = []
    deadline = time.monotonic() + max(5, wait_seconds)
    while time.monotonic() < deadline:
        messages = _paged_items(
            client,
            "/open-apis/im/v1/messages",
            operation="轮询查宝回复",
            params={
                "container_id_type": "chat",
                "container_id": settings.feishu_chat_target_chat_id,
                "sort_type": "ByCreateTimeDesc",
                "page_size": 50,
            },
            max_pages=1,
        )
        replies = [
            message
            for message in messages
            if _sender_id(message) == settings.feishu_chat_agent_sender_id
            and sent_message_id
            in {
                _string(message.get("parent_id")),
                _string(message.get("root_id")),
            }
        ]
        if replies:
            break
        time.sleep(3)

    file_reply = next((message for message in replies if message.get("msg_type") == "file"), None)
    file_probe: dict[str, Any] = {"attempted": False}
    if file_reply is not None:
        candidate = _file_candidate(file_reply)
        if candidate:
            file_probe = {
                "attempted": True,
                **client.probe_tenant_resource(*candidate),
            }

    return {
        "step": "user_flow",
        "runtime": feishu_chat_runtime_summary(settings),
        "oauth": {
            "required_scopes_granted": True,
            "refresh_rotation_verified": True,
        },
        "mention_preflight": mention_preflight,
        "send": {
            "sent_as_user": True,
            "message_fingerprint": chat_target_fingerprint(sent_message_id),
            "marker": marker,
        },
        "reply": {
            "found": bool(replies),
            "count": len(replies),
            "types": sorted({_string(item.get("msg_type")) or "<unknown>" for item in replies}),
            "parent_or_root_matches": bool(replies),
        },
        "file_resource_probe": file_probe,
    }


def _paged_items(
    client: Phase0Client,
    path: str,
    *,
    operation: str,
    params: dict[str, Any],
    max_pages: int = 20,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token: str | None = None
    for _ in range(max_pages):
        query = dict(params)
        if page_token:
            query["page_token"] = page_token
        payload = client.tenant_get(path, operation=operation, params=query)
        data = _data_dict(payload)
        batch = data.get("items") or []
        if isinstance(batch, list):
            items.extend(item for item in batch if isinstance(item, dict))
        if not data.get("has_more"):
            break
        page_token = _string(data.get("page_token"))
        if not page_token:
            break
    return items


def _capture_paged_items(
    client: Phase0Client,
    path: str,
    *,
    operation: str,
    params: dict[str, Any],
    max_pages: int = 20,
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        return (
            _paged_items(
                client,
                path,
                operation=operation,
                params=params,
                max_pages=max_pages,
            ),
            None,
        )
    except Phase0VerificationError as exc:
        return [], str(exc)


def _analyze_messages(messages: list[dict[str, Any]], settings: Settings) -> dict[str, Any]:
    mention_messages = [item for item in messages if isinstance(item.get("mentions"), list)]
    parent_count = sum(bool(_string(item.get("parent_id"))) for item in messages)
    root_count = sum(bool(_string(item.get("root_id"))) for item in messages)
    sender_ids = {_sender_id(item) for item in messages if _sender_id(item)}
    agent_messages = [
        item
        for item in messages
        if settings.feishu_chat_agent_sender_id
        and _sender_id(item) == settings.feishu_chat_agent_sender_id
    ]
    return {
        "sample_count": len(messages),
        "message_types": sorted(
            {_string(item.get("msg_type")) or "<unknown>" for item in messages}
        ),
        "sender_id_present": all(bool(_sender_id(item)) for item in messages),
        "sender_identity_count": len(sender_ids),
        "mentions_field_count": len(mention_messages),
        "parent_id_count": parent_count,
        "root_id_count": root_count,
        "agent_sender_configured": bool(settings.feishu_chat_agent_sender_id),
        "agent_message_count": len(agent_messages),
        "agent_message_types": sorted(
            {_string(item.get("msg_type")) or "<unknown>" for item in agent_messages}
        ),
        "configured_mention": _analyze_configured_mention(messages, settings),
    }


def _analyze_configured_mention(
    messages: list[dict[str, Any]], settings: Settings
) -> dict[str, Any]:
    mention_id = settings.feishu_chat_agent_mention_id.strip()
    if not mention_id:
        return {
            "configured": False,
            "matching_message_count": 0,
            "mention_entry_count": 0,
            "id_types": [],
            "display_name_matches": False,
            "body_placeholder_present_count": 0,
            "placeholder_key_patterns": [],
        }

    matching_message_count = 0
    mention_entry_count = 0
    id_types: set[str] = set()
    display_names: list[str] = []
    body_placeholder_present_count = 0
    placeholder_key_patterns: set[str] = set()

    for message in messages:
        mentions = message.get("mentions")
        if not isinstance(mentions, list):
            continue
        matched_entries = [
            mention
            for mention in mentions
            if isinstance(mention, dict) and _string(mention.get("id")) == mention_id
        ]
        if not matched_entries:
            continue

        matching_message_count += 1
        mention_entry_count += len(matched_entries)
        text = _message_body_text(message)
        placeholder_found = False
        for mention in matched_entries:
            id_type = _string(mention.get("id_type"))
            if id_type:
                id_types.add(id_type)
            display_name = _string(mention.get("name"))
            if display_name:
                display_names.append(display_name)
            key = _string(mention.get("key"))
            if key:
                placeholder_key_patterns.add(_mention_key_pattern(key))
                if text and key in text:
                    placeholder_found = True
        if placeholder_found:
            body_placeholder_present_count += 1

    return {
        "configured": True,
        "matching_message_count": matching_message_count,
        "mention_entry_count": mention_entry_count,
        "id_types": sorted(id_types),
        "display_name_matches": bool(display_names)
        and all(
            name == settings.feishu_chat_agent_display_name for name in display_names
        ),
        "body_placeholder_present_count": body_placeholder_present_count,
        "placeholder_key_patterns": sorted(placeholder_key_patterns),
    }


def _preflight_user_flow_target(
    client: Phase0Client, settings: Settings
) -> dict[str, Any]:
    target = client.tenant_get(
        f"/open-apis/im/v1/chats/{settings.feishu_chat_target_chat_id}",
        operation="发送前复核测试群信息",
    )
    chat = _data_dict(target)
    if _string(chat.get("name")) != settings.feishu_chat_target_chat_name:
        raise Phase0VerificationError("发送前目标群名称复核失败，已停止发送")
    if _string(chat.get("chat_status")) != "normal":
        raise Phase0VerificationError("发送前目标群状态不是 normal，已停止发送")

    messages = _paged_items(
        client,
        "/open-apis/im/v1/messages",
        operation="发送前复核查宝 mention",
        params={
            "container_id_type": "chat",
            "container_id": settings.feishu_chat_target_chat_id,
            "sort_type": "ByCreateTimeDesc",
            "page_size": 50,
        },
        max_pages=4,
    )
    mention = _analyze_configured_mention(messages, settings)
    if mention["matching_message_count"] < 1:
        raise Phase0VerificationError("最近 200 条消息中未找到配置的查宝 mention，已停止发送")
    if "open_id" not in mention["id_types"]:
        raise Phase0VerificationError("查宝 mention 的历史 id_type 不是 open_id，已停止发送")
    if mention["body_placeholder_present_count"] < 1:
        raise Phase0VerificationError("查宝 mention 与历史消息正文占位符不一致，已停止发送")
    return {
        "target_name_matches": True,
        "target_status": "normal",
        "historical_mention_verified": True,
        "mention_id_type": "open_id",
        "send_content_format": "at_tag",
    }


def _build_user_test_text(settings: Settings, marker: str) -> str:
    mention_id = html.escape(settings.feishu_chat_agent_mention_id.strip(), quote=True)
    display_name = html.escape(settings.feishu_chat_agent_display_name.strip(), quote=False)
    return (
        f'<at user_id="{mention_id}">{display_name}</at> '
        f"{marker} 请回复一条简短确认消息；如测试环境允许，请同时返回一个小型 Excel 文件。"
    )


def _message_body_text(message: dict[str, Any]) -> str | None:
    body = message.get("body")
    content = body.get("content") if isinstance(body, dict) else None
    if not isinstance(content, str):
        return None
    try:
        parsed = json.loads(content)
    except ValueError:
        return None
    return _string(parsed.get("text")) if isinstance(parsed, dict) else None


def _mention_key_pattern(key: str) -> str:
    if re.fullmatch(r"@_user_\d+", key):
        return "@_user_N"
    return "other"


def _find_agent_file_candidate(
    messages: list[dict[str, Any]], agent_sender_id: str
) -> tuple[str, str] | None:
    if not agent_sender_id:
        return None
    for message in messages:
        if _sender_id(message) != agent_sender_id:
            continue
        candidate = _file_candidate(message)
        if candidate:
            return candidate
    return None


def _file_candidate(message: dict[str, Any]) -> tuple[str, str] | None:
    if message.get("msg_type") != "file":
        return None
    message_id = _string(message.get("message_id"))
    body = message.get("body")
    content = body.get("content") if isinstance(body, dict) else None
    if not message_id or not isinstance(content, str):
        return None
    try:
        parsed = json.loads(content)
    except ValueError:
        return None
    file_key = _string(parsed.get("file_key")) if isinstance(parsed, dict) else None
    if not file_key:
        return None
    return message_id, file_key


def _consume_oauth_state(settings: Settings) -> str:
    if not OAUTH_STATE_PATH.is_file():
        raise Phase0VerificationError("未找到阶段 0 OAuth state，请先运行 oauth-url")
    try:
        payload = json.loads(OAUTH_STATE_PATH.read_text(encoding="utf-8"))
    finally:
        OAUTH_STATE_PATH.unlink(missing_ok=True)
    if not isinstance(payload, dict):
        raise Phase0VerificationError("阶段 0 OAuth state 文件格式异常")
    if payload.get("target_fingerprint") != settings.feishu_chat_target_fingerprint:
        raise Phase0VerificationError("OAuth state 绑定的目标群已发生变化")
    created_at = datetime.fromisoformat(str(payload.get("created_at")))
    age_seconds = (datetime.now(timezone.utc) - created_at).total_seconds()
    if age_seconds < 0 or age_seconds > 600:
        raise Phase0VerificationError("阶段 0 OAuth state 已过期")
    state = _string(payload.get("state"))
    if not state:
        raise Phase0VerificationError("阶段 0 OAuth state 缺失")
    return state


def _required_process_secret(name: str) -> str:
    import os

    value = os.environ.get(name, "").strip()
    if not value:
        raise Phase0VerificationError(f"缺少进程环境变量 {name}")
    return value


def _required_token_field(payload: dict[str, Any], name: str) -> str:
    value = _string(payload.get(name)) or _string(_data_dict(payload).get(name))
    if not value:
        raise Phase0VerificationError(f"OAuth 响应缺少 {name}")
    return value


def _scope_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [item for item in value.replace(",", " ").split() if item]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def _sender_id(message: dict[str, Any]) -> str | None:
    sender = message.get("sender")
    if not isinstance(sender, dict):
        return None
    return _string(sender.get("id")) or _string(sender.get("sender_id"))


def _data_dict(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    return data if isinstance(data, dict) else {}


def _string(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _feishu_error_detail(
    payload: dict[str, Any], operation: str, response: httpx.Response
) -> str:
    code = payload.get("code")
    raw_message = payload.get("msg") or payload.get("message") or "飞书拒绝请求"
    message = _sanitize_feishu_message(str(raw_message))
    error = payload.get("error")
    error_dict = error if isinstance(error, dict) else {}
    log_id = (
        error_dict.get("log_id")
        or payload.get("request_id")
        or response.headers.get("x-tt-logid")
    )
    parts = [f"HTTP {response.status_code}"]
    if code is not None:
        parts.append(f"code {code}")
    if log_id:
        parts.append(f"log_id {log_id}")
    return f"{operation}失败 ({', '.join(parts)}): {message}"


def _sanitize_feishu_message(message: str) -> str:
    without_urls = re.sub(r"https?://\S+", "<console link omitted>", message)
    return re.sub(r"cli_[A-Za-z0-9]+", "<app_id>", without_urls)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="查宝测试群阶段 0 验证工具")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("discover", help="只读列出应用 B 已加入的群")
    readonly = subparsers.add_parser("readonly", help="验证目标测试群、成员和历史消息")
    readonly.add_argument("--probe-file-resource", action="store_true")
    readonly.add_argument("--message-pages", type=int, default=1)
    subparsers.add_parser("oauth-url", help="生成用户增量授权地址")
    user_flow = subparsers.add_parser("user-flow", help="刷新用户 token、发送并轮询查宝回复")
    user_flow.add_argument("--confirm", required=True)
    user_flow.add_argument("--wait-seconds", type=int, default=90)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = Settings()
    try:
        if args.command == "discover":
            report = command_discover(settings)
        elif args.command == "readonly":
            report = command_readonly(
                settings,
                probe_file_resource=args.probe_file_resource,
                message_pages=args.message_pages,
            )
        elif args.command == "oauth-url":
            report = command_oauth_url(settings)
        else:
            report = command_user_flow(
                settings,
                confirmation=args.confirm,
                wait_seconds=args.wait_seconds,
            )
    except Phase0VerificationError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    except RuntimeError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1
    print(json.dumps({"ok": True, **report}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
