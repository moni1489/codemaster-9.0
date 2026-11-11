"""Выдача цифровых копий с проверкой прав на каждый запрос (D-004).

404 — документ/файл не существует или его описание не опубликовано (не раскрываем существование).
403 — карточка опубликована, но копия закрыта/ограничена, либо запрошена мастер-копия.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.access import PUBLIC_FILE_KINDS, document_visible
from app.core.db import get_session
from app.core.logging import log
from app.media import storage
from app.models import Branch, Collection, DigitalFile, Document, Exhibit, Exhibition, News, Person

router = APIRouter(prefix="/api/media", tags=["media"])


async def _site_media_public(session: AsyncSession, file_id: uuid.UUID) -> bool:
    """Файл без привязки к документу публичен, только если на него ссылается опубликованный объект."""
    published_exhibit = (
        select(Exhibit.id)
        .join(Exhibition, Exhibition.id == Exhibit.exhibition_id)
        .where(Exhibit.image_file_id == file_id, Exhibition.workflow_status == "published")
    )
    checks = [
        exists(published_exhibit),
        exists(
            select(Exhibition.id).where(Exhibition.cover_file_id == file_id, Exhibition.workflow_status == "published")
        ),
        exists(select(News.id).where(News.cover_file_id == file_id, News.workflow_status == "published")),
        exists(
            select(Collection.id).where(Collection.cover_file_id == file_id, Collection.workflow_status == "published")
        ),
        exists(select(Person.id).where(Person.portrait_file_id == file_id, Person.workflow_status == "published")),
        exists(select(Branch.id).where(Branch.photo_file_id == file_id, Branch.visible.is_(True))),
    ]
    return bool((await session.execute(select(or_(*checks)))).scalar())


async def check_public_file(session: AsyncSession, file_id: uuid.UUID) -> DigitalFile:
    f = await session.get(DigitalFile, file_id)
    if f is None:
        raise HTTPException(404, "Файл не найден")
    if f.document_id is None:
        if f.kind in PUBLIC_FILE_KINDS and await _site_media_public(session, file_id):
            return f
        raise HTTPException(404, "Файл не найден")

    doc = (
        await session.execute(select(Document).where(Document.id == f.document_id, document_visible()))
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, "Файл не найден")
    if f.kind not in PUBLIC_FILE_KINDS or doc.file_access != "open":
        log.info("media_denied", file_id=str(file_id), reason="access")
        raise HTTPException(403, "Доступ к цифровой копии ограничен")
    return f


@router.get("/{file_id}", response_class=FileResponse)
async def get_media(file_id: uuid.UUID, session: AsyncSession = Depends(get_session)) -> FileResponse:
    f = await check_public_file(session, file_id)
    path = storage.resolve(f.storage_key)
    if not path.is_file():
        log.error("media_missing_on_disk", file_id=str(file_id))
        raise HTTPException(404, "Файл не найден")
    return FileResponse(
        path,
        media_type=f.mime,
        headers={
            # копии документов кэшируются коротко и только браузером: статус доступа может измениться
            "Cache-Control": "private, max-age=300" if f.document_id else "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
            "Content-Disposition": "inline",
        },
    )
