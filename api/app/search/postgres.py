"""PostgreSQL FTS + pg_trgm. Индекс (search_index) содержит только публично видимые документы."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    delete,
    exists,
    false,
    func,
    literal,
    literal_column,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.access import document_visible
from app.models import (
    Branch,
    DigitalFile,
    Document,
    DocumentTranslation,
    FundTranslation,
    SearchIndex,
)
from app.search.base import SearchHit, SearchPage, SearchParams
from app.search.synonyms import expand, load_synonyms

RU: Any = literal_column("'russian'::regconfig")
SIMPLE: Any = literal_column("'simple'::regconfig")
FUZZY_THRESHOLD = 0.45


WEIGHTS: dict[str, Any] = {w: literal_column(f"'{w}'::\"char\"") for w in "ABCD"}  # константы, не ввод


def _tsv(config: Any, text: str, weight: str) -> Any:
    return func.setweight(func.to_tsvector(config, func.unaccent(text)), WEIGHTS[weight])


def _query_for_alt(alt: str) -> Any:
    return func.plainto_tsquery(RU, func.unaccent(alt)).op("||")(func.plainto_tsquery(SIMPLE, func.unaccent(alt)))


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _tr_ilike(column: Any, value: str) -> ColumnElement[bool]:
    pattern = f"%{_escape_like(value.strip())}%"
    return exists(
        select(DocumentTranslation.entity_id).where(
            DocumentTranslation.entity_id == Document.id, column.ilike(pattern, escape="\\")
        )
    )


class PostgresSearchBackend:
    # ---------- индексация ----------
    async def index_document(self, session: AsyncSession, document_id: uuid.UUID) -> bool:
        doc = (
            await session.execute(select(Document).where(Document.id == document_id, document_visible()))
        ).scalar_one_or_none()
        if doc is None:
            await session.execute(delete(SearchIndex).where(SearchIndex.document_id == document_id))
            return False
        fund_trs = (
            (await session.execute(select(FundTranslation).where(FundTranslation.entity_id == doc.fund_id)))
            .scalars()
            .all()
        )
        trs = [t for t in doc.translations if t.translation_status != "missing"]
        titles = " ".join(t.title for t in trs)
        rest_parts: list[str] = []
        for t in trs:
            rest_parts += [
                t.summary or "",
                t.historical_note or "",
                t.author_org or "",
                t.place or "",
                t.topic or "",
                t.period_label or "",
            ]
        rest_parts += list(doc.tags) + [f.title for f in fund_trs if f.translation_status != "missing"]
        rest = " ".join(p for p in rest_parts if p)
        cipher = f"{doc.cipher} {doc.fund_number}"
        search_text = " ".join([titles, rest, cipher]).lower()
        tsv = (
            _tsv(RU, titles, "A")
            .op("||")(_tsv(SIMPLE, titles, "A"))
            .op("||")(_tsv(RU, rest, "B"))
            .op("||")(_tsv(SIMPLE, rest, "C"))
            .op("||")(_tsv(SIMPLE, cipher, "A"))
        )
        stmt = insert(SearchIndex).values(document_id=doc.id, tsv=tsv, search_text=search_text)
        stmt = stmt.on_conflict_do_update(
            index_elements=[SearchIndex.document_id],
            set_={
                "tsv": stmt.excluded.tsv,
                "search_text": stmt.excluded.search_text,
                "updated_at": func.now(),
            },
        )
        await session.execute(stmt)
        return True

    async def rebuild(self, session: AsyncSession) -> int:
        await session.execute(delete(SearchIndex))
        ids = (await session.execute(select(Document.id).where(document_visible()))).scalars().all()
        for doc_id in ids:
            await self.index_document(session, doc_id)
        return len(ids)

    # ---------- поиск ----------
    def _filters(self, p: SearchParams) -> list[ColumnElement[bool]]:
        f: list[ColumnElement[bool]] = []
        if p.title:
            f.append(_tr_ilike(DocumentTranslation.title, p.title))
        if p.author:
            f.append(_tr_ilike(DocumentTranslation.author_org, p.author))
        if p.topic:
            f.append(
                or_(_tr_ilike(DocumentTranslation.topic, p.topic), Document.tags.contains([p.topic.strip().lower()]))
            )
        if p.place:
            f.append(_tr_ilike(DocumentTranslation.place, p.place))
        if p.fund:
            f.append(func.upper(Document.fund_number) == p.fund.strip().upper())
        if p.inventory:
            f.append(Document.inventory_number == p.inventory.strip())
        if p.case:
            f.append(Document.case_number == p.case.strip())
        year_to = func.coalesce(Document.year_to, Document.year_from)
        if p.year is not None:
            f.append(and_(Document.year_from <= p.year, year_to >= p.year))
        if p.period_from is not None:
            f.append(year_to >= p.period_from)
        if p.period_to is not None:
            f.append(Document.year_from <= p.period_to)
        if p.doc_type:
            f.append(Document.doc_type.in_(p.doc_type))
        if p.category:
            f.append(Document.category.in_(p.category))
        if p.personal is not None:
            f.append(Document.is_personal_fund.is_(p.personal))
        if p.branch:
            f.append(Document.branch_id.in_(select(Branch.id).where(Branch.slug == p.branch)))
        if p.has_copy:
            f.append(
                and_(
                    Document.file_access == "open",
                    exists(
                        select(DigitalFile.id).where(DigitalFile.document_id == Document.id, DigitalFile.kind == "view")
                    ),
                )
            )
        return f

    def _base(self, p: SearchParams) -> Select[Any]:
        # INNER JOIN на индекс — гарантия, что в выдаче только публичные документы
        return (
            select(Document.id)
            .join(SearchIndex, SearchIndex.document_id == Document.id)
            .where(document_visible(), *self._filters(p))
        )

    def _order(self, stmt: Select[Any], p: SearchParams, rank: Any) -> Select[Any]:
        if p.sort == "date_asc":
            return stmt.order_by(Document.year_from.asc().nulls_last(), Document.cipher)
        if p.sort == "date_desc":
            return stmt.order_by(Document.year_from.desc().nulls_last(), Document.cipher)
        if p.sort == "cipher":
            return stmt.order_by(Document.fund_number, Document.cipher)
        return stmt.order_by(rank.desc(), Document.year_from.asc().nulls_last(), Document.cipher)

    async def _run(self, session: AsyncSession, stmt: Select[Any], p: SearchParams) -> tuple[list[SearchHit], int]:
        total = (await session.execute(select(func.count()).select_from(stmt.subquery()))).scalar_one()
        offset = (max(p.page, 1) - 1) * p.page_size
        rows = (await session.execute(stmt.limit(p.page_size).offset(offset))).all()
        return [SearchHit(document_id=r[0], rank=float(r[1] or 0)) for r in rows], int(total)

    async def search(self, session: AsyncSession, params: SearchParams) -> SearchPage:
        q = (params.q or "").strip()
        if not q:
            stmt = self._base(params).add_columns(literal(0.0).label("rank"))
            sort = params.sort if params.sort != "relevance" else "date_asc"
            stmt = self._order(stmt, SearchParams(sort=sort), literal(0.0))
            hits, total = await self._run(session, stmt, params)
            return SearchPage(hits=hits, total=total)

        expansion = expand(q, await load_synonyms(session))
        tsquery: Any = None
        for group in expansion.groups:
            alt_q: Any = None
            for alt in group:
                one = _query_for_alt(alt)
                alt_q = one if alt_q is None else alt_q.op("||")(one)
            tsquery = alt_q if tsquery is None else tsquery.op("&&")(alt_q)
        match: ColumnElement[bool] = SearchIndex.tsv.op("@@")(tsquery) if tsquery is not None else false()
        rank = func.ts_rank_cd(SearchIndex.tsv, tsquery) if tsquery is not None else literal(0.0)
        stmt = self._order(self._base(params).where(match).add_columns(rank.label("rank")), params, rank)
        hits, total = await self._run(session, stmt, params)
        if total:
            return SearchPage(hits=hits, total=total, expanded_terms=expansion.applied)

        # Фолбэк по опечаткам: триграммное сходство с текстом индекса
        sim = func.word_similarity(func.unaccent(q.lower()), func.unaccent(SearchIndex.search_text))
        stmt = self._order(self._base(params).where(sim >= FUZZY_THRESHOLD).add_columns(sim.label("rank")), params, sim)
        hits, total = await self._run(session, stmt, params)
        return SearchPage(hits=hits, total=total, fuzzy=bool(total), expanded_terms=expansion.applied)


_backend = PostgresSearchBackend()


def get_search_backend() -> PostgresSearchBackend:
    return _backend
