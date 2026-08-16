from __future__ import annotations

import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import (  # noqa: E402
    production_web_security_blockers,
    settings,
)


def main() -> int:
    blockers = production_web_security_blockers(settings)
    public_origin_valid = "app_public_url_must_be_https_origin" not in blockers
    login_redirect_matches = (
        public_origin_valid and "feishu_redirect_uri_mismatch" not in blockers
    )
    chat_redirect_matches = (
        public_origin_valid
        and "feishu_chat_oauth_redirect_uri_mismatch" not in blockers
    )
    print("Production web security readiness")
    print(f"app_environment={settings.app_environment}")
    print(f"cookie_secure={str(settings.cookie_secure).lower()}")
    print(f"public_https_origin={str(public_origin_valid).lower()}")
    print(f"login_redirect_matches={str(login_redirect_matches).lower()}")
    print(f"chat_redirect_matches={str(chat_redirect_matches).lower()}")
    print(f"jwt_secret_valid={str('jwt_secret_invalid' not in blockers).lower()}")
    for blocker in blockers:
        print(f"blocker={blocker}")
    readiness = "ready" if not blockers else "blocked"
    print(f"production_web_security={readiness}")
    return 0 if not blockers else 1


if __name__ == "__main__":
    raise SystemExit(main())
