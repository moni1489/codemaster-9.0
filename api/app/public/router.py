"""Публичные справочники: филиалы и календарь памятных дат."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.service import media_url, tr_info
from app.core.db import get_session
from app.core.i18n import lang_param, pick
from app.models import Branch, MemorialDate
from app.public import schemas as s

router = APIRouter(prefix="/api", tags=["public"])
Session = Annotated[AsyncSession, Depends(get_session)]
Lang = Annotated[str, Depends(lang_param)]


def branch_out(b: Branch, lang: str) -> s.BranchOut:
    p = pick(b.translations, lang)
    assert p is not None
    tr = p.tr
    extra: Any = b.phones_extra
    return s.BranchOut(
        id=b.id,
        slug=b.slug,
        type=b.type,
        name=tr.name,
        short_name=tr.short_name,
        locality=tr.locality,
        address=tr.address,
        hours=tr.hours,
        hours_verified=b.hours_verified,
        director=b.director,
        phone=b.phone,
        phones_extra=extra,
        email=b.email,
        lat=b.lat,
        lon=b.lon,
        coords_verified=b.coords_verified,
        photo_url=media_url(b.photo_file_id) if b.photo_file_id else None,
        description=tr.description,
        translation=tr_info(p),
    )


@router.get("/branches", response_model=list[s.BranchOut])
async def list_branches(session: Session, lang: Lang) -> list[s.BranchOut]:
    rows = (
        (await session.execute(select(Branch).where(Branch.visible.is_(True)).order_by(Branch.sort_order)))
        .scalars()
        .all()
    )
    return [branch_out(b, lang) for b in rows]


@router.get("/branches/{slug}", response_model=s.BranchOut)
async def get_branch(slug: str, session: Session, lang: Lang) -> s.BranchOut:
    b = (
        await session.execute(select(Branch).where(Branch.slug == slug, Branch.visible.is_(True)))
    ).scalar_one_or_none()
    if b is None:
        raise HTTPException(404, "Филиал не найден")
    return branch_out(b, lang)


def _md_out(m: MemorialDate, lang: str) -> s.MemorialDateOut | None:
    p = pick(m.translations, lang)
    if p is None:
        return None
    return s.MemorialDateOut(
        id=m.id,
        year=m.year,
        month=m.month,
        day=m.day,
        date_label=p.tr.date_label,
        title=p.tr.title,
        source=m.source,
        translation=tr_info(p),
    )


@router.get("/memorial-dates/today", response_model=s.TodayOut)
async def memorial_today(
    session: Session,
    lang: Lang,
    on: Annotated[date | None, Query(description="Дата (по умолчанию — сегодня)")] = None,
    limit: Annotated[int, Query(ge=1, le=20)] = 5,
) -> s.TodayOut:
    today = on or date.today()
    rows = (await session.execute(select(MemorialDate).where(MemorialDate.month == today.month))).scalars().all()
    exact = [m for m in rows if m.day == today.day]
    picked = exact
    if not exact:
        # ближайшие события этого месяца (сначала предстоящие)
        picked = sorted(
            (m for m in rows if m.day is not None),
            key=lambda m: ((m.day or 0) < today.day, abs((m.day or 0) - today.day)),
        )
    # одна и та же годовщина повторяется в календарях разных лет — берём самую свежую формулировку
    seen: set[tuple[int | None, str]] = set()
    items: list[s.MemorialDateOut] = []
    for m in sorted(picked, key=lambda m: -m.year):
        out = _md_out(m, lang)
        if out is None:
            continue
        key = (m.day, out.title[:40])
        if key in seen:
            continue
        seen.add(key)
        items.append(out)
        if len(items) >= limit:
            break
    return s.TodayOut(date=today.strftime("%m-%d"), exact=bool(exact), items=items)


@router.get("/memorial-dates", response_model=list[s.MemorialDateOut])
async def memorial_dates(
    session: Session,
    lang: Lang,
    year: Annotated[int, Query(ge=2022, le=2030)],
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
) -> list[s.MemorialDateOut]:
    stmt = select(MemorialDate).where(MemorialDate.year == year)
    if month is not None:
        stmt = stmt.where(MemorialDate.month == month)
    rows = (await session.execute(stmt.order_by(MemorialDate.month.nulls_last(), MemorialDate.day))).scalars().all()
    return [o for o in (_md_out(m, lang) for m in rows) if o is not None]
