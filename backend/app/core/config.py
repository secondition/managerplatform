from functools import lru_cache
import base64
import binascii
from hashlib import sha256
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./storage/app.db"
    jwt_secret: str = Field(default="change-me")
    access_token_ttl_minutes: int = 120
    refresh_token_ttl_days: int = 14
    cookie_secure: bool = False
    tz: str = "Asia/Shanghai"

    feishu_app_id: str = ""
    feishu_app_secret: str = ""
    feishu_redirect_uri: str = "http://localhost:5173/login/callback"
    feishu_api_base: str = "https://open.feishu.cn"
    feishu_sync_profile_on_login: bool = True
    feishu_notification_enabled: bool = False
    app_public_url: str = "http://localhost:5173"
    app_environment: Literal["development", "test", "production"] = "development"

    feishu_chat_enabled: bool = False
    feishu_chat_phase0_enabled: bool = False
    feishu_chat_environment: Literal["test", "production"] = "test"
    feishu_chat_target_chat_id: str = ""
    feishu_chat_target_chat_name: str = ""
    feishu_chat_agent_sender_id: str = ""
    feishu_chat_agent_mention_id: str = ""
    feishu_chat_agent_display_name: str = "查宝"
    feishu_chat_production_confirmation: str = ""
    feishu_chat_oauth_redirect_uri: str = "http://localhost:5173/chat/oauth/callback"
    feishu_chat_initial_backfill_days: int = Field(default=30, ge=1, le=365)
    feishu_chat_sync_interval_seconds: int = Field(default=3, ge=1, le=3600)
    feishu_chat_member_sync_interval_seconds: int = Field(default=300, ge=30, le=86400)
    feishu_chat_member_snapshot_max_age_seconds: int = Field(default=600, ge=60, le=604800)
    feishu_chat_cache_retention_days: int = Field(default=180, ge=1, le=3650)
    feishu_chat_attachment_max_bytes: int = Field(default=52_428_800, ge=1, le=1_073_741_824)
    feishu_chat_send_text_max_length: int = Field(default=5000, ge=1, le=50_000)
    feishu_chat_token_refresh_skew_seconds: int = Field(default=300, ge=30, le=3600)
    feishu_credential_encryption_key: str = ""

    # 飞书 OAuth2（新版）端点/参数，均可在 .env 覆盖，上线前以飞书控制台/文档为准。
    # 授权页在 accounts.feishu.cn，token/user_info 在 open.feishu.cn（feishu_api_base）。
    feishu_authorize_base: str = "https://accounts.feishu.cn"
    feishu_authorize_path: str = "/open-apis/authen/v1/authorize"
    feishu_token_path: str = "/open-apis/authen/v2/oauth/token"
    feishu_user_info_path: str = "/open-apis/authen/v1/user_info"
    # 空格分隔的 scope；至少需要能拉到 user_info。上线前在控制台申请对应权限。
    feishu_oauth_scope: str = "contact:user.base:readonly"
    feishu_tenant_token_path: str = "/open-apis/auth/v3/tenant_access_token/internal"
    feishu_contact_dept_path: str = "/open-apis/contact/v3/departments"
    feishu_contact_user_path: str = "/open-apis/contact/v3/users"

    owner_feishu_union_id: str = ""
    default_member_permissions: str = ""
    # 顶层部门优先级：一个人属于多个同为顶层的部门时，按此顺序择优显示。
    department_priority: str = "总经办,市场运营部,产品管理部"

    @field_validator("database_url")
    @classmethod
    def resolve_sqlite_path(cls, value: str) -> str:
        prefix = "sqlite:///"
        if not value.startswith(prefix):
            return value
        raw_path = value[len(prefix):]
        if not raw_path or raw_path == ":memory:":
            return value
        path = Path(raw_path)
        if path.is_absolute():
            return value
        return f"{prefix}{(BACKEND_DIR / path).resolve().as_posix()}"

    @property
    def default_permissions(self) -> list[str]:
        return [item.strip() for item in self.default_member_permissions.split(",") if item.strip()]

    @property
    def department_priority_list(self) -> list[str]:
        return [item.strip() for item in self.department_priority.split(",") if item.strip()]

    @property
    def feishu_chat_target_fingerprint(self) -> str:
        return chat_target_fingerprint(self.feishu_chat_target_chat_id)

    @property
    def feishu_chat_expected_production_confirmation(self) -> str:
        fingerprint = self.feishu_chat_target_fingerprint
        return f"PRODUCTION:{fingerprint}" if fingerprint else ""

    def build_authorize_url(self, state: str) -> str:
        """Full Feishu authorize URL for the QR-login flow.

        Uses urlencode (never manual string concat) per Feishu's guidance.
        """
        from urllib.parse import urlencode

        query = urlencode(
            {
                "client_id": self.feishu_app_id,
                "response_type": "code",
                "redirect_uri": self.feishu_redirect_uri,
                "scope": self.feishu_oauth_scope,
                "state": state,
            }
        )
        return f"{self.feishu_authorize_base}{self.feishu_authorize_path}?{query}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


def production_web_security_blockers(candidate: Settings = settings) -> list[str]:
    if candidate.app_environment != "production":
        return ["app_environment_not_production"]

    blockers: list[str] = []
    if not candidate.cookie_secure:
        blockers.append("cookie_secure_not_enabled")
    if candidate.jwt_secret == "change-me" or len(candidate.jwt_secret) < 32:
        blockers.append("jwt_secret_invalid")

    public_origin = _production_https_origin(candidate.app_public_url)
    if public_origin is None:
        blockers.append("app_public_url_must_be_https_origin")
        return blockers

    expected_login_redirect = f"{public_origin}/login/callback"
    expected_chat_redirect = f"{public_origin}/chat/oauth/callback"
    if candidate.feishu_redirect_uri.strip() != expected_login_redirect:
        blockers.append("feishu_redirect_uri_mismatch")
    if candidate.feishu_chat_oauth_redirect_uri.strip() != expected_chat_redirect:
        blockers.append("feishu_chat_oauth_redirect_uri_mismatch")
    return blockers


def validate_security_settings(candidate: Settings = settings) -> None:
    if candidate.app_environment == "production":
        blockers = production_web_security_blockers(candidate)
        if blockers:
            raise RuntimeError(
                "Invalid production web security settings: " + ", ".join(blockers)
            )
        return

    if candidate.cookie_secure and (
        candidate.jwt_secret == "change-me" or len(candidate.jwt_secret) < 32
    ):
        raise RuntimeError("JWT_SECRET must be a non-default value of at least 32 characters")


def cors_allowed_origins(candidate: Settings = settings) -> list[str]:
    if candidate.app_environment == "production":
        origin = _production_https_origin(candidate.app_public_url)
        return [origin] if origin else []
    return ["http://localhost:5173", "http://127.0.0.1:5173"]


def _production_https_origin(value: str) -> str | None:
    normalized = value.strip()
    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError:
        return None
    hostname = (parsed.hostname or "").lower().rstrip(".")
    if (
        parsed.scheme.lower() != "https"
        or not parsed.netloc
        or not hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
        or parsed.path not in {"", "/"}
        or hostname == "localhost"
        or hostname.endswith(".localhost")
        or hostname in {"127.0.0.1", "::1"}
    ):
        return None
    default_port = port in {None, 443}
    host = f"[{hostname}]" if ":" in hostname else hostname
    return f"https://{host}" if default_port else f"https://{host}:{port}"


def chat_target_fingerprint(chat_id: str) -> str:
    normalized = chat_id.strip()
    if not normalized:
        return ""
    return sha256(normalized.encode("utf-8")).hexdigest()[:12]


def validate_feishu_chat_settings(
    candidate: Settings = settings,
    *,
    require_target: bool = False,
    require_phase0: bool = False,
) -> None:
    if require_phase0 and not candidate.feishu_chat_phase0_enabled:
        raise RuntimeError("FEISHU_CHAT_PHASE0_ENABLED must be true for phase 0 verification")
    if require_phase0 and candidate.feishu_chat_environment != "test":
        raise RuntimeError("Phase 0 verification is restricted to FEISHU_CHAT_ENVIRONMENT=test")
    if (
        candidate.feishu_chat_phase0_enabled
        and candidate.feishu_chat_environment != "test"
    ):
        raise RuntimeError("FEISHU_CHAT_PHASE0_ENABLED requires FEISHU_CHAT_ENVIRONMENT=test")
    if candidate.feishu_chat_phase0_enabled and candidate.app_environment == "production":
        raise RuntimeError("Phase 0 verification cannot run in APP_ENVIRONMENT=production")

    if not candidate.feishu_chat_enabled and not require_target:
        return

    missing = [
        name
        for name, value in (
            ("FEISHU_APP_ID", candidate.feishu_app_id),
            ("FEISHU_APP_SECRET", candidate.feishu_app_secret),
        )
        if not value.strip()
    ]
    if missing:
        raise RuntimeError(f"Missing Feishu chat settings: {', '.join(missing)}")

    if require_target:
        missing_agent_settings = [
            name
            for name, value in (
                ("FEISHU_CHAT_TARGET_CHAT_ID", candidate.feishu_chat_target_chat_id),
                ("FEISHU_CHAT_TARGET_CHAT_NAME", candidate.feishu_chat_target_chat_name),
                ("FEISHU_CHAT_AGENT_SENDER_ID", candidate.feishu_chat_agent_sender_id),
                ("FEISHU_CHAT_AGENT_MENTION_ID", candidate.feishu_chat_agent_mention_id),
                ("FEISHU_CHAT_AGENT_DISPLAY_NAME", candidate.feishu_chat_agent_display_name),
            )
            if not value.strip()
        ]
        if missing_agent_settings:
            raise RuntimeError(
                f"Missing Feishu chat settings: {', '.join(missing_agent_settings)}"
            )

    if candidate.app_environment == "production" and candidate.feishu_chat_environment != "production":
        raise RuntimeError(
            "APP_ENVIRONMENT=production requires FEISHU_CHAT_ENVIRONMENT=production"
        )
    if candidate.app_environment != "production" and candidate.feishu_chat_environment == "production":
        raise RuntimeError(
            "Production Feishu chat cannot run outside APP_ENVIRONMENT=production"
        )
    if (
        candidate.feishu_chat_environment == "production"
        and candidate.feishu_chat_target_chat_id.strip()
    ):
        expected = candidate.feishu_chat_expected_production_confirmation
        if not expected or candidate.feishu_chat_production_confirmation != expected:
            raise RuntimeError(
                "FEISHU_CHAT_PRODUCTION_CONFIRMATION must match the configured target fingerprint"
            )
    if candidate.feishu_chat_enabled and not _is_valid_fernet_key(
        candidate.feishu_credential_encryption_key
    ):
        raise RuntimeError(
            "FEISHU_CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key when chat is enabled"
        )
    if candidate.feishu_chat_enabled and (
        candidate.jwt_secret == "change-me" or len(candidate.jwt_secret) < 32
    ):
        raise RuntimeError(
            "JWT_SECRET must be a non-default value of at least 32 characters when chat is enabled"
        )


def _is_valid_fernet_key(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return False
    try:
        decoded = base64.urlsafe_b64decode(normalized.encode("ascii"))
    except (UnicodeEncodeError, binascii.Error, ValueError):
        return False
    return len(decoded) == 32


def feishu_chat_runtime_summary(candidate: Settings = settings) -> dict[str, str | bool]:
    return {
        "app_environment": candidate.app_environment,
        "chat_enabled": candidate.feishu_chat_enabled,
        "phase0_enabled": candidate.feishu_chat_phase0_enabled,
        "chat_environment": candidate.feishu_chat_environment,
        "target_name": candidate.feishu_chat_target_chat_name or "<unset>",
        "target_fingerprint": candidate.feishu_chat_target_fingerprint or "<unset>",
    }
