"""Публичный API электронного каталога (ТЗ §5.3). Все выборки — через предикаты app.catalog.access."""

from __future__ import annotations

import math
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog import schemas as s
from app.catalog.access import case_visible, document_visible, fund_visible, inventory_visible
from app.catalog.service import branch_refs, document_card, list_items, tr_info
from app.core.db import get_session
from app.core.i18n import Picked, lang_param, pick
from app.models import ArchiveCase, Branch, Document, Fund, Inventory, SearchLog
from app.models.enums import CATEGORIES, DOC_TYPES
from app.search.base import SearchParams, SortKey
from app.search.postgres import get_search_backend

router = APIRouter(prefix="/api/catalog", tags=["catalog"])
Session = Annotated[AsyncSession, Depends(get_session)]
Lang = Annotated[str, Depends(lang_param)]
NOT_FOUND = "Запись не найдена или не опубликована"


def _clean(value: str | None, max_len: int = 200) -> str | None:
    value = (value or "").strip()
    return value[:max_len] or None


@router.get("/search", response_model=s.SearchResponse)
async def search(
    session: Session,
    lang: Lang,
    q: Annotated[str | None, Query(max_length=300, description="Ключевые слова")] = None,
    title: Annotated[str | None, Query(max_length=200)] = None,
    fund: Annotated[str | None, Query(max_length=32)] = None,
    inventory: Annotated[str | None, Query(max_length=32)] = None,
    case: Annotated[str | None, Query(max_length=32)] = None,
    period_from: Annotated[int | None, Query(ge=1000, le=2100)] = None,
    period_to: Annotated[int | None, Query(ge=1000, le=2100)] = None,
    year: Annotated[int | None, Query(ge=1000, le=2100)] = None,
    author: Annotated[str | None, Query(max_length=200)] = None,
    topic: Annotated[str | None, Query(max_length=200)] = None,
    place: Annotated[str | None, Query(max_length=200)] = None,
    doc_type: Annotated[list[str] | None, Query()] = None,
    category: Annotated[list[str] | None, Query()] = None,
    branch: Annotated[str | None, Query(max_length=64)] = None,
    personal: bool | None = None,
    has_copy: bool | None = None,
    sort: SortKey = "relevance",
    page: Annotated[int, Query(ge=1, le=1000)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
) -> s.SearchResponse:
    params = SearchParams(
        q=_clean(q, 300),
        title=_clean(title),
        fund=_clean(fund),
        inventory=_clean(inventory),
        case=_clean(case),
        period_from=period_from,
        period_to=period_to,
        year=year,
        author=_clean(author),
        topic=_clean(topic),
        place=_clean(place),
        doc_type=tuple(t for t in (doc_type or []) if t in DOC_TYPES),
        category=tuple(c for c in (category or []) if c in CATEGORIES),
        branch=_clean(branch),
        personal=personal,
        has_copy=has_copy,
        sort=sort,
        page=page,
        page_size=page_size,
        lang=lang,
    )
    result = await get_search_backend().search(session, params)
    ids = [h.document_id for h in result.hits]
    docs_by_id = {d.id: d for d in (await session.execute(select(Document).where(Document.id.in_(ids)))).scalars()}
    docs = [docs_by_id[i] for i in ids if i in docs_by_id]
    if params.q:
        session.add(SearchLog(query=params.q[:300], lang=lang, source="catalog", results_count=result.total))
        await session.commit()
    return s.SearchResponse(
        items=await list_items(session, docs, lang),
        total=result.total,
        page=page,
        page_size=page_size,
        pages=math.ceil(result.total / page_size) if result.total else 0,
        fuzzy=result.fuzzy,
        expanded_terms=result.expanded_terms,
    )


@router.get("/facets", response_model=s.Facets)
async def facets(session: Session, lang: Lang) -> s.Facets:
    vis = document_visible()
    cats = (await session.execute(select(Document.category, func.count()).where(vis).group_by(Document.category))).all()
    types = (
        await session.execute(select(Document.doc_type, func.count()).where(vis).group_by(Document.doc_type))
    ).all()
    br = (
        await session.execute(
            select(Branch.slug, func.count())
            .join(Document, Document.branch_id == Branch.id)
            .where(vis)
            .group_by(Branch.slug)
        )
    ).all()
    names = {b.slug: b.name for b in (await branch_refs(session, lang)).values()}
    years = (await session.execute(select(func.min(Document.year_from), func.max(Document.year_to)).where(vis))).one()
    personal = (
        await session.execute(select(func.count()).where(vis, Document.is_personal_fund.is_(True)))
    ).scalar_one()
    return s.Facets(
        categories=[s.FacetValue(value=v, count=c) for v, c in cats],
        doc_types=[s.FacetValue(value=v, count=c) for v, c in types],
        branches=[s.FacetValue(value=v, count=c, label=names.get(v)) for v, c in br],
        year_min=years[0],
        year_max=years[1],
        personal_funds=personal,
    )


@router.get("/documents/{doc_id}", response_model=s.DocumentCard)
async def get_document(doc_id: uuid.UUID, session: Session, lang: Lang) -> s.DocumentCard:
    doc = (
        await session.execute(select(Document).where(Document.id == doc_id, document_visible()))
    ).scalar_one_or_none()
    if doc is None:
        raise HTTPException(404, NOT_FOUND)
    return await document_card(session, doc, lang)


async def _counts(session: AsyncSession, stmt: Select[tuple[uuid.UUID, int]]) -> dict[uuid.UUID, int]:
    return {key: int(n) for key, n in (await session.execute(stmt)).all()}


def _pick_any(e: Fund | Inventory | ArchiveCase, lang: str) -> Picked[Any] | None:
    translations: list[Any] = list(e.translations)
    return pick(translations, lang, e.original_lang)


async def _documents_where(session: AsyncSession, lang: str, *conds: ColumnElement[bool]) -> list[s.DocumentListItem]:
    stmt = select(Document).where(document_visible(), *conds).order_by(Document.cipher)
    docs = (await session.execute(stmt)).scalars().all()
    return await list_items(session, docs, lang)


def _node(
    level: str,
    e: Fund | Inventory | ArchiveCase,
    lang: str,
    parents: list[s.Ref],
    children: list[s.ChildItem],
    documents: list[s.DocumentListItem],
    branch: s.BranchRef | None = None,
    is_personal: bool = False,
) -> s.HierarchyNode:
    p = _pick_any(e, lang)
    assert p is not None
    tr = p.tr
    return s.HierarchyNode(
        level=level,
        id=e.id,
        number=e.number,
        cipher=e.cipher,
        title=tr.title,
        summary=getattr(tr, "summary", None),
        historical_note=getattr(tr, "historical_note", None),
        restricted_note=getattr(tr, "restricted_note", None),
        year_from=e.year_from,
        year_to=e.year_to,
        is_personal_fund=is_personal,
        is_demo=e.is_demo,
        branch=branch,
        parents=parents,
        children=children,
        documents=documents,
        translation=tr_info(p),
    )


def _child(e: Inventory | ArchiveCase, lang: str, count: int | None) -> s.ChildItem:
    p = _pick_any(e, lang)
    return s.ChildItem(
        id=e.id, number=e.number, cipher=e.cipher, title=p.tr.title if p else e.cipher,
        year_from=e.year_from, year_to=e.year_to, count=count,
    )  # fmt: skip


def _ref(e: Fund | Inventory | ArchiveCase, lang: str) -> s.Ref:
    p = _pick_any(e, lang)
    return s.Ref(id=e.id, number=e.number, cipher=e.cipher, title=p.tr.title if p else e.cipher)


@router.get("/funds", response_model=list[s.ChildItem])
async def list_funds(session: Session, lang: Lang, personal: bool | None = None) -> list[s.ChildItem]:
    stmt = select(Fund).where(fund_visible()).order_by(Fund.number)
    if personal is not None:
        stmt = stmt.where(Fund.is_personal_fund.is_(personal))
    funds = (await session.execute(stmt)).scalars().all()
    counts = await _counts(
        session,
        select(Document.fund_id, func.count()).where(document_visible()).group_by(Document.fund_id),
    )
    out = []
    for f in funds:
        p = _pick_any(f, lang)
        out.append(
            s.ChildItem(
                id=f.id,
                number=f.number,
                cipher=f.cipher,
                title=p.tr.title if p else f.cipher,
                year_from=f.year_from,
                year_to=f.year_to,
                count=counts.get(f.id, 0),
            )  # fmt: skip
        )
    return out


@router.get("/funds/{fund_id}", response_model=s.HierarchyNode)
async def get_fund(fund_id: uuid.UUID, session: Session, lang: Lang) -> s.HierarchyNode:
    fund = (await session.execute(select(Fund).where(Fund.id == fund_id, fund_visible()))).scalar_one_or_none()
    if fund is None:
        raise HTTPException(404, NOT_FOUND)
    invs = (
        (
            await session.execute(
                select(Inventory).where(Inventory.fund_id == fund.id, inventory_visible()).order_by(Inventory.number)
            )
        )
        .scalars()
        .all()
    )
    counts = await _counts(
        session,
        select(Document.inventory_id, func.count())
        .where(document_visible(), Document.fund_id == fund.id)
        .group_by(Document.inventory_id),
    )
    branches = await branch_refs(session, lang)
    return _node(
        "fund", fund, lang, [], [_child(i, lang, counts.get(i.id, 0)) for i in invs], [],
        branches.get(fund.branch_id) if fund.branch_id else None, fund.is_personal_fund,
    )  # fmt: skip


@router.get("/inventories/{inv_id}", response_model=s.HierarchyNode)
async def get_inventory(inv_id: uuid.UUID, session: Session, lang: Lang) -> s.HierarchyNode:
    inv = (
        await session.execute(select(Inventory).where(Inventory.id == inv_id, inventory_visible()))
    ).scalar_one_or_none()
    if inv is None:
        raise HTTPException(404, NOT_FOUND)
    fund = await session.get(Fund, inv.fund_id)
    assert fund is not None
    cases = (
        (
            await session.execute(
                select(ArchiveCase)
                .where(ArchiveCase.inventory_id == inv.id, case_visible())
                .order_by(ArchiveCase.number)
            )
        )
        .scalars()
        .all()
    )
    counts = await _counts(
        session,
        select(Document.case_id, func.count())
        .where(document_visible(), Document.inventory_id == inv.id)
        .group_by(Document.case_id),
    )
    return _node(
        "inventory", inv, lang, [_ref(fund, lang)], [_child(c, lang, counts.get(c.id, 0)) for c in cases], [],
        is_personal=fund.is_personal_fund,
    )  # fmt: skip


@router.get("/cases/{case_id}", response_model=s.HierarchyNode)
async def get_case(case_id: uuid.UUID, session: Session, lang: Lang) -> s.HierarchyNode:
    case = (
        await session.execute(select(ArchiveCase).where(ArchiveCase.id == case_id, case_visible()))
    ).scalar_one_or_none()
    if case is None:
        raise HTTPException(404, NOT_FOUND)
    inv = await session.get(Inventory, case.inventory_id)
    assert inv is not None
    fund = await session.get(Fund, inv.fund_id)
    assert fund is not None
    docs = await _documents_where(session, lang, Document.case_id == case.id)
    return _node("case", case, lang, [_ref(fund, lang), _ref(inv, lang)], [], docs, is_personal=fund.is_personal_fund)
