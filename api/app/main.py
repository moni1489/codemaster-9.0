"""Точка входа FastAPI."""

from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import get_engine
from app.core.logging import configure_logging, log


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

    return app


app = create_app()
