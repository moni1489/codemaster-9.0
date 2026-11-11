"""Интерфейс поискового бэкенда. Реализация по умолчанию — PostgreSQL FTS (D-006).

Замена на OpenSearch = новая реализация этого протокола; публичный API каталога не меняется.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Literal, Protocol

from sqlalchemy.ext.asyncio import AsyncSession

SortKey = Literal["relevance", "date_asc", "date_desc", "cipher"]


@dataclass(frozen=True)
class SearchParams:
    q: str | None = None  # ключевые слова / свободный текст
    title: str | None = None
    fund: str | None = None
    inventory: str | None = None
    case: str | None = None
    period_from: int | None = None
    period_to: int | None = None
    year: int | None = None
    author: str | None = None
    topic: str | None = None
    place: str | None = None
    doc_type: tuple[str, ...] = ()
    category: tuple[str, ...] = ()
    branch: str | None = None  # slug
    personal: bool | None = None
    has_copy: bool | None = None
    sort: SortKey = "relevance"
    page: int = 1
    page_size: int = 20
    lang: str = "ru"


@dataclass
class SearchHit:
    document_id: uuid.UUID
    rank: float


@dataclass
class SearchPage:
    hits: list[SearchHit]
    total: int
    fuzzy: bool = False  # результаты по нечёткому совпадению (опечатки)
    expanded_terms: list[str] = field(default_factory=list)  # применённые синонимы


class SearchBackend(Protocol):
    async def search(self, session: AsyncSession, params: SearchParams) -> SearchPage: ...

    async def index_document(self, session: AsyncSession, document_id: uuid.UUID) -> bool:
        """Переиндексировать документ. Возвращает True, если документ попал в индекс (виден публично)."""
        ...

    async def rebuild(self, session: AsyncSession) -> int: ...
