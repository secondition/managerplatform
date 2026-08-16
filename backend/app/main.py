from contextlib import asynccontextmanager
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1.router import api_router
from app.core.config import (
    cors_allowed_origins,
    feishu_chat_runtime_summary,
    settings,
    validate_feishu_chat_settings,
    validate_security_settings,
)
from app.core.scheduler import shutdown_scheduler, start_scheduler
from app.core.chat_sync_worker import (
    shutdown_chat_sync_worker,
    start_chat_sync_worker,
)


logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_security_settings()
    validate_feishu_chat_settings()
    if settings.feishu_chat_enabled or settings.feishu_chat_phase0_enabled:
        logger.warning("Feishu chat runtime: %s", feishu_chat_runtime_summary())
    try:
        start_scheduler()
        start_chat_sync_worker()
        yield
    finally:
        await shutdown_chat_sync_worker()
        shutdown_scheduler()


app = FastAPI(title="Manager Platform API", version="0.1.0", lifespan=lifespan)
FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
FRONTEND_ENTRY_HEADERS = {
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

UPLOADS_DIR = Path(__file__).resolve().parents[1] / "storage" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


if FRONTEND_DIST.exists():
    assets_dir = FRONTEND_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="frontend-assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    def serve_frontend(full_path: str) -> FileResponse:
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API route not found")
        requested = FRONTEND_DIST / full_path
        if requested.is_file():
            headers = FRONTEND_ENTRY_HEADERS if requested.name == "index.html" else None
            return FileResponse(requested, headers=headers)
        return FileResponse(FRONTEND_DIST / "index.html", headers=FRONTEND_ENTRY_HEADERS)
