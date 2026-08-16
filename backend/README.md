# Manager Platform Backend

FastAPI backend for the enterprise work-management platform: Feishu OAuth login,
contact sync, daily reports, traffic-light weekly metrics, OKR, subscriptions,
personal profiles, admin management, and company settings.

## Local setup

```powershell
..\.venv\Scripts\python -m pip install --only-binary=:all: -r requirements.txt
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m uvicorn app.main:app --reload
```

The `--only-binary=:all:` flag keeps Python 3.14 installs on prebuilt wheels and prevents slow source builds.
Create a dedicated local `.env` before starting the development server. The
committed `.env.example` is intentionally a production handover template and
must not be copied unchanged for local development.

All API routes are mounted under `/api/v1`.

## Login

The only login path is Feishu QR-code OAuth. Configure the Feishu app first — see `飞书应用接入与配置指引.md` at the repo root for creating the self-built app, the redirect-URL whitelist, scopes, and the `.env` values.

Initial owner bootstrap uses `OWNER_FEISHU_UNION_ID`; the old email/password
login path is not part of the current implementation.

For production deployments, copy `.env.example` to the private `.env`, then
replace every required blank value before starting the service. Set
`COOKIE_SECURE=true`, configure a unique
`JWT_SECRET` of at least 32 characters, and set `APP_PUBLIC_URL` to the public
HTTPS origin. The Feishu login and chat OAuth callbacks must exactly match
`<APP_PUBLIC_URL>/login/callback` and
`<APP_PUBLIC_URL>/chat/oauth/callback`. Production startup fails closed when
any of these settings are missing or inconsistent. OAuth state is browser-bound,
and refresh tokens rotate on refresh and are revoked when an employee is disabled.

## Runtime storage

Uploaded company logos and user avatars are served from `/uploads` and stored
under `backend/storage/uploads/`. They are runtime data and should not be
committed to Git. Raster uploads are verified by decoded image format, MIME,
extension, and dimensions; SVG uploads are rejected.

## Feishu chat synchronization

The AI-brain Feishu chat integration uses an application-identity polling worker
started by the FastAPI lifespan only when `FEISHU_CHAT_ENABLED=true`. It performs
an initial bounded backfill, incremental message polling with persisted page
cursors, periodic `open_id` member snapshots, rate-limit backoff, and projection
retention cleanup. A cross-process file lock keeps the SQLite deployment to one
chat-sync owner. Keep the switch disabled until the production target,
independent credential-encryption key, Feishu permissions, deployment preflight,
and limited production acceptance have been verified. Production must use the
target confirmation described in the repository guide.

The Feishu app used by the platform must have both a base message-read scope
(`im:message` or `im:message:readonly`) and `im:message.group_msg`; the latter is
required for application-identity reads of all group messages. A missing group
message scope commonly appears as Feishu error `230027`: user-identity sends can
still succeed and the agent can reply in Feishu, but the polling worker cannot
read either message back into the platform. After changing scopes, complete
administrator approval and publish a new app version before retrying.

### Optional chat tuning

The production `.env.example` intentionally omits chat tuning variables because
the application already provides stable defaults. Add an override to the private
production `.env` only when there is a reviewed operational requirement:

```dotenv
FEISHU_CHAT_INITIAL_BACKFILL_DAYS=30
FEISHU_CHAT_SYNC_INTERVAL_SECONDS=3
FEISHU_CHAT_MEMBER_SYNC_INTERVAL_SECONDS=300
FEISHU_CHAT_MEMBER_SNAPSHOT_MAX_AGE_SECONDS=600
FEISHU_CHAT_CACHE_RETENTION_DAYS=180
FEISHU_CHAT_ATTACHMENT_MAX_BYTES=52428800
FEISHU_CHAT_SEND_TEXT_MAX_LENGTH=5000
FEISHU_CHAT_TOKEN_REFRESH_SKEW_SECONDS=300
```

Changes require a backend restart. Keep the member snapshot maximum age greater
than the member synchronization interval so temporary API delays do not make a
fresh membership snapshot appear stale.
