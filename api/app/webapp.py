"""Раздача собранного фронтенда (web/dist) самим API — режим одного контейнера (Render).

Отдаются только статические ассеты сборки; хранилище архивных файлов по-прежнему НЕ монтируется
(только /api/media с проверкой прав). Неизвестные пути вне /api → index.html (SPA).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https://*.tile.openstreetmap.org; font-src 'self'; connect-src 'self'; "
    "frame-ancestors 'none'; object-src 'none'; base-uri 'self'; form-action 'self'"
)
SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Strict-Transport-Security": "max-age=31536000",
    "Permissions-Policy": "geolocation=(self), camera=(), microphone=()",
}


def mount_web(app: FastAPI, dist: Path) -> None:
    dist = dist.resolve()
    index = dist / "index.html"
    if not index.is_file():
        return
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.middleware("http")
    async def security_headers(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        response = await call_next(request)
        for k, v in SECURITY_HEADERS.items():
            response.headers.setdefault(k, v)
        if request.url.path.startswith(("/admin", "/api")):
            response.headers["X-Robots-Tag"] = "noindex, nofollow"
        return response

    @app.get("/{path:path}", include_in_schema=False)
    async def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            from fastapi import HTTPException

            raise HTTPException(404, "Not Found")
        candidate = (dist / path).resolve()
        if path and dist in candidate.parents and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
