"""Точка входа FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import text

from app.admin.branches import router as admin_branches
from app.admin.catalog import router as admin_catalog
from app.admin.content import router as admin_content
from app.admin.system import router as admin_system
from app.ai.router import router as ai_router
from app.auth.router import router as auth_router
from app.catalog.router import router as catalog_router
from app.cms.router import router as cms_router
from app.core.config import get_settings
from app.core.db import get_engine
from app.core.logging import configure_logging, log
from app.media.router import router as media_router
from app.public.router import router as public_router


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(
        title="ГА ВКО — API прототипа",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    @app.get("/api/health", tags=["system"])
    async def health() -> dict[str, str]:
        db_state = "ok"
        try:
            async with get_engine().connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception as exc:  # отчёт о состоянии не должен падать
            log.warning("health_db_unavailable", error=type(exc).__name__)
            db_state = "unavailable"
        return {"status": "ok", "db": db_state, "llm_provider": get_settings().llm_provider}

    app.include_router(catalog_router)
    for r in (ai_router, auth_router, admin_branches, admin_catalog, admin_content, admin_system):
        app.include_router(r)
    app.include_router(cms_router)
    app.include_router(media_router)
    app.include_router(public_router)
    return app


app = create_app()
