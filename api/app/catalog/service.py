"""Сборка публичных DTO каталога. Вызывается только для записей, уже прошедших document_visible()."""

from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import schemas as s
from app.core.i18n import Picked, pick
from app.models import ArchiveCase, Branch, DigitalFile, Document, Fund, Inventory


def media_url(file_id: uuid.UUID) -> str:
    return f"/api/media/{file_id}"


def tr_info(p: Picked[Any]) -> s.TranslationInfo:
    return s.TranslationInfo(requested_lang=p.requested_lang, lang=p.lang, status=p.status, is_fallback=p.is_fallback)


async def branch_refs(session: AsyncSession, lang: str) -> dict[uuid.UUID, s.BranchRef]:
    branches = (await session.execute(select(Branch))).scalars().all()
    out: dict[uuid.UUID, s.BranchRef] = {}
    for b in branches:
        p = pick(b.translations, lang)
        out[b.id] = s.BranchRef(id=b.id, slug=b.slug, name=p.tr.short_name if p else b.slug)
    return out


async def _files_by_doc(session: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[DigitalFile]]:
    if not ids:
        return {}
    rows = (
        (
            await session.execute(
                select(DigitalFile).where(DigitalFile.document_id.in_(ids)).order_by(DigitalFile.page_no)
            )
        )
        .scalars()
        .all()
    )
    out: dict[uuid.UUID, list[DigitalFile]] = defaultdict(list)
    for f in rows:
        if f.document_id is not None:
            out[f.document_id].append(f)
    return out


def _list_item(
    d: Document, lang: str, files: list[DigitalFile], branches: dict[uuid.UUID, s.BranchRef]
) -> s.DocumentListItem:
    p = pick(d.translations, lang, d.original_lang)
    assert p is not None, "документ без перевода на исходном языке"
    thumb = next((f for f in files if f.kind == "thumb"), None)
    return s.DocumentListItem(
        id=d.id,
        cipher=d.cipher,
        title=p.tr.title,
        summary=p.tr.summary,
        period_label=p.tr.period_label,
        year_from=d.year_from,
        year_to=d.year_to,
        date_verified=d.date_verified,
        category=d.category,
        doc_type=d.doc_type,
        file_access=d.file_access,
        has_digital_copy=any(f.kind == "master" for f in files),
        thumb_url=media_url(thumb.id) if thumb and d.file_access == "open" else None,
        fund_number=d.fund_number,
        is_personal_fund=d.is_personal_fund,
        is_demo=d.is_demo,
        branch=branches.get(d.branch_id) if d.branch_id else None,
        translation=tr_info(p),
    )


async def list_items(session: AsyncSession, docs: Sequence[Document], lang: str) -> list[s.DocumentListItem]:
    files = await _files_by_doc(session, [d.id for d in docs])
    branches = await branch_refs(session, lang)
    return [_list_item(d, lang, files.get(d.id, []), branches) for d in docs]


def _ref(entity: Fund | Inventory | ArchiveCase, lang: str) -> s.Ref:
    translations: list[Any] = list(entity.translations)
    p = pick(translations, lang, entity.original_lang)
    return s.Ref(id=entity.id, number=entity.number, cipher=entity.cipher, title=p.tr.title if p else entity.cipher)


async def document_card(session: AsyncSession, d: Document, lang: str) -> s.DocumentCard:
    p = pick(d.translations, lang, d.original_lang)
    assert p is not None
    case = await session.get(ArchiveCase, d.case_id)
    inventory = await session.get(Inventory, d.inventory_id)
    fund = await session.get(Fund, d.fund_id)
    assert case and inventory and fund
    files = (await _files_by_doc(session, [d.id])).get(d.id, [])
    branches = await branch_refs(session, lang)
    is_open = d.file_access == "open"
    thumbs = {f.page_no: f for f in files if f.kind == "thumb"}
    pages = (
        [
            s.Page(
                id=f.id,
                page_no=f.page_no,
                url=media_url(f.id),
                thumb_url=media_url(thumbs[f.page_no].id) if f.page_no in thumbs else None,
                width=f.width,
                height=f.height,
            )
            for f in files
            if f.kind == "view"
        ]
        if is_open
        else []
    )
    return s.DocumentCard(
        id=d.id,
        cipher=d.cipher,
        title=p.tr.title,
        summary=p.tr.summary,
        historical_note=p.tr.historical_note,
        period_label=p.tr.period_label,
        date_from=d.date_from,
        date_to=d.date_to,
        year_from=d.year_from,
        year_to=d.year_to,
        date_verified=d.date_verified,
        category=d.category,
        doc_type=d.doc_type,
        language=d.language,
        sheets=d.sheets,
        sheets_count=d.sheets_count,
        storage_location=d.storage_location,
        author_org=p.tr.author_org,
        place=p.tr.place,
        topic=p.tr.topic,
        tags=list(d.tags),
        file_access=d.file_access,
        access_conditions=p.tr.access_conditions,
        has_digital_copy=any(f.kind == "master" for f in files),
        pages=pages,
        fund=_ref(fund, lang),
        inventory=_ref(inventory, lang),
        case=_ref(case, lang),
        branch=branches.get(d.branch_id) if d.branch_id else None,
        is_personal_fund=d.is_personal_fund,
        is_demo=d.is_demo,
        translation=tr_info(p),
    )
