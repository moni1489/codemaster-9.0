"""Публичный API онлайн-выставок и цифровой истории региона (ТЗ §5.6, §5.7, §8.2)."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.access import document_visible
from app.catalog.schemas import TranslationInfo
from app.catalog.service import media_url, tr_info
from app.core.db import get_session
from app.core.i18n import lang_param, pick
from app.models import Collection, Document, Event, Exhibition, Person

router = APIRouter(prefix="/api", tags=["history"])
Session = Annotated[AsyncSession, Depends(get_session)]
Lang = Annotated[str, Depends(lang_param)]
PUB = "published"


class DocLink(BaseModel):
    id: uuid.UUID
    cipher: str
    title: str


async def _visible_docs(session: AsyncSession, ids: list[uuid.UUID], lang: str) -> dict[uuid.UUID, DocLink]:
    """Ссылки только на документы, видимые публично (выставка не раскрывает закрытое)."""
    if not ids:
        return {}
    rows = (await session.execute(select(Document).where(Document.id.in_(ids), document_visible()))).scalars()
    out = {}
    for d in rows:
        p = pick(d.translations, lang, d.original_lang)
        out[d.id] = DocLink(id=d.id, cipher=d.cipher, title=p.tr.title if p else d.cipher)
    return out


class ExhibitOut(BaseModel):
    id: uuid.UUID
    order: int
    caption: str
    description: str | None
    image_url: str | None
    source_text: str | None
    rights_note: str | None
    document: DocLink | None
    translation: TranslationInfo


class ExhibitionOut(BaseModel):
    slug: str
    title: str
    summary: str | None
    body: str | None
    topic: str | None
    period_from: int | None
    period_to: int | None
    cover_url: str | None
    is_demo: bool
    exhibits: list[ExhibitOut]
    translation: TranslationInfo


async def _exhibition(session: AsyncSession, e: Exhibition, lang: str, full: bool) -> ExhibitionOut:
    p = pick(e.translations, lang, e.original_lang)
    assert p is not None
    exhibits: list[ExhibitOut] = []
    if full:
        docs = await _visible_docs(session, [x.document_id for x in e.exhibits if x.document_id], lang)
        for x in e.exhibits:
            xp = pick(x.translations, lang)
            if xp is None:
                continue
            exhibits.append(ExhibitOut(
                id=x.id, order=x.sort_order, caption=xp.tr.caption, description=xp.tr.description,
                image_url=media_url(x.image_file_id) if x.image_file_id else None, source_text=x.source_text,
                rights_note=x.rights_note, document=docs.get(x.document_id) if x.document_id else None,
                translation=tr_info(xp),
            ))  # fmt: skip
    return ExhibitionOut(
        slug=e.slug, title=p.tr.title, summary=p.tr.summary, body=p.tr.body, topic=e.topic,
        period_from=e.period_from, period_to=e.period_to,
        cover_url=media_url(e.cover_file_id) if e.cover_file_id else None, is_demo=e.is_demo,
        exhibits=exhibits, translation=tr_info(p),
    )  # fmt: skip


@router.get("/exhibitions", response_model=list[ExhibitionOut])
async def exhibitions(session: Session, lang: Lang) -> list[ExhibitionOut]:
    rows = (await session.execute(select(Exhibition).where(Exhibition.workflow_status == PUB))).scalars().all()
    return [await _exhibition(session, e, lang, False) for e in rows]


@router.get("/exhibitions/{slug}", response_model=ExhibitionOut)
async def exhibition(slug: str, session: Session, lang: Lang) -> ExhibitionOut:
    e = (
        await session.execute(select(Exhibition).where(Exhibition.slug == slug, Exhibition.workflow_status == PUB))
    ).scalar_one_or_none()
    if e is None:
        raise HTTPException(404, "Выставка не найдена")
    return await _exhibition(session, e, lang, True)


class PersonOut(BaseModel):
    slug: str
    name: str
    role_line: str | None
    bio: str | None
    source: str | None
    birth_label: str | None
    death_label: str | None
    dates_verified: bool
    is_fictional: bool
    portrait_url: str | None
    translation: TranslationInfo


def _person(x: Person, lang: str) -> PersonOut | None:
    p = pick(x.translations, lang, x.original_lang)
    if p is None:
        return None
    return PersonOut(
        slug=x.slug, name=p.tr.name, role_line=p.tr.role_line, bio=p.tr.bio, source=p.tr.source,
        birth_label=x.birth_label, death_label=x.death_label, dates_verified=x.dates_verified,
        is_fictional=x.is_fictional, portrait_url=media_url(x.portrait_file_id) if x.portrait_file_id else None,
        translation=tr_info(p),
    )  # fmt: skip


class CollectionOut(BaseModel):
    slug: str
    title: str
    summary: str | None
    editorial_note: str | None
    topic: str | None
    cover_url: str | None
    is_demo: bool
    documents: list[DocLink]
    persons: list[PersonOut]
    translation: TranslationInfo


@router.get("/history/collections", response_model=list[CollectionOut])
async def collections(session: Session, lang: Lang) -> list[CollectionOut]:
    rows = (await session.execute(select(Collection).where(Collection.workflow_status == PUB))).scalars().all()
    people = {x.id: x for x in (await session.execute(select(Person).where(Person.workflow_status == PUB))).scalars()}
    out = []
    for c in rows:
        p = pick(c.translations, lang, c.original_lang)
        if p is None:
            continue
        docs = await _visible_docs(session, [i.document_id for i in c.items if i.document_id], lang)
        persons = [_person(people[i.person_id], lang) for i in c.items if i.person_id in people]
        out.append(CollectionOut(
            slug=c.slug, title=p.tr.title, summary=p.tr.summary, editorial_note=p.tr.editorial_note, topic=c.topic,
            cover_url=media_url(c.cover_file_id) if c.cover_file_id else None, is_demo=c.is_demo,
            documents=[docs[i.document_id] for i in c.items if i.document_id in docs],
            persons=[x for x in persons if x], translation=tr_info(p),
        ))  # fmt: skip
    return out


@router.get("/history/persons", response_model=list[PersonOut])
async def persons(session: Session, lang: Lang) -> list[PersonOut]:
    rows = (await session.execute(select(Person).where(Person.workflow_status == PUB))).scalars()
    return [x for x in (_person(p, lang) for p in rows) if x]


class EventOut(BaseModel):
    id: uuid.UUID
    year: int
    year_to: int | None
    title: str
    description: str | None
    place: str | None
    source: str | None
    topic: str
    date_verified: bool
    is_editorial: bool
    document: DocLink | None
    translation: TranslationInfo


@router.get("/history/timeline", response_model=list[EventOut])
async def timeline(
    session: Session,
    lang: Lang,
    topic: str | None = Query(None, max_length=64),
    year_from: int | None = Query(None, ge=1500, le=2100),
    year_to: int | None = Query(None, ge=1500, le=2100),
) -> list[EventOut]:
    stmt = select(Event).where(Event.workflow_status == PUB).order_by(Event.year)
    if topic:
        stmt = stmt.where(Event.topic == topic)
    if year_from:
        stmt = stmt.where(Event.year >= year_from)
    if year_to:
        stmt = stmt.where(Event.year <= year_to)
    rows = (await session.execute(stmt)).scalars().all()
    docs = await _visible_docs(session, [e.document_id for e in rows if e.document_id], lang)
    out: list[EventOut] = []
    for e in rows:
        p = pick(e.translations, lang, e.original_lang)
        if p is None:
            continue
        doc: Any = docs.get(e.document_id) if e.document_id else None
        out.append(EventOut(
            id=e.id, year=e.year, year_to=e.year_to, title=p.tr.title, description=p.tr.description,
            place=p.tr.place, source=p.tr.source, topic=e.topic, date_verified=e.date_verified,
            is_editorial=e.is_editorial, document=doc, translation=tr_info(p),
        ))  # fmt: skip
    return out
