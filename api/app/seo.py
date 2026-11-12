"""sitemap.xml: только публично видимые карточки и разделы, с hreflang (ТЗ §7.5). Закрытое и админка не попадают."""

from __future__ import annotations

from typing import Annotated
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.db import get_session
from app.models import Document, SearchIndex

router = APIRouter(tags=["seo"])
SECTIONS = ["", "/catalog", "/catalog/funds", "/about", "/services", "/services/state", "/services/paid", "/visitors",
            "/history", "/exhibitions", "/news", "/branches", "/faq"]  # fmt: skip


def _url(base: str, path: str) -> str:
    alts = "".join(
        f'<xhtml:link rel="alternate" hreflang="{lg}" href="{escape(base)}/{lg}{escape(path)}"/>'
        for lg in ("kk", "ru", "en")
    )
    return f"<url><loc>{escape(base)}/ru{escape(path)}</loc>{alts}</url>"


@router.get("/sitemap.xml", include_in_schema=False)
async def sitemap(session: Annotated[AsyncSession, Depends(get_session)]) -> Response:
    base = get_settings().site_url.rstrip("/")
    ids = (
        await session.execute(select(Document.id).join(SearchIndex, SearchIndex.document_id == Document.id))
    ).scalars()
    urls = [_url(base, s) for s in SECTIONS] + [_url(base, f"/catalog/documents/{i}") for i in ids]
    xml = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
           'xmlns:xhtml="http://www.w3.org/1999/xhtml">' + "".join(urls) + "</urlset>")  # fmt: skip
    return Response(xml, media_type="application/xml")
