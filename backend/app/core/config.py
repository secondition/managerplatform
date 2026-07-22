from functools import lru_cache
from pathlib import Path

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
    department_priority: str = ""

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


def validate_security_settings() -> None:
    if settings.cookie_secure and (
        settings.jwt_secret == "change-me" or len(settings.jwt_secret) < 32
    ):
        raise RuntimeError("JWT_SECRET must be a non-default value of at least 32 characters")
