# Manager Platform Backend

FastAPI backend for the enterprise work-management platform: Feishu OAuth login,
contact sync, daily reports, traffic-light weekly metrics, OKR, subscriptions,
personal profiles, admin management, and company settings.

## Local setup

```powershell
..\.venv\Scripts\python -m pip install --only-binary=:all: -r requirements.txt
Copy-Item .env.example .env
..\.venv\Scripts\python -m alembic upgrade head
..\.venv\Scripts\python -m uvicorn app.main:app --reload
```

The `--only-binary=:all:` flag keeps Python 3.14 installs on prebuilt wheels and prevents slow source builds.

All API routes are mounted under `/api/v1`.

## Login

The only login path is Feishu QR-code OAuth. Configure the Feishu app first — see `飞书应用接入与配置指引.md` at the repo root for creating the self-built app, the redirect-URL whitelist, scopes, and the `.env` values.

Initial owner bootstrap uses `OWNER_FEISHU_UNION_ID`; the old email/password
login path is not part of the current implementation.

For HTTPS deployments set `COOKIE_SECURE=true` and configure a unique
`JWT_SECRET` of at least 32 characters. Startup rejects the default/short secret
when secure cookies are enabled. OAuth state is browser-bound, and refresh
tokens rotate on refresh and are revoked when an employee is disabled.

## Runtime storage

Uploaded company logos and user avatars are served from `/uploads` and stored
under `backend/storage/uploads/`. They are runtime data and should not be
committed to Git. Raster uploads are verified by decoded image format, MIME,
extension, and dimensions; SVG uploads are rejected.
