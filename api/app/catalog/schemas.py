"""Публичные DTO каталога. Поля мастер-файлов и служебные статусы закрытых записей сюда не попадают."""

from __future__ import annotations

import uuid
from datetime import date

from pydantic import BaseModel


class TranslationInfo(BaseModel):
    requested_lang: str
    lang: str
    status: str  # original | verified | machine | missing
    is_fallback: bool


class Ref(BaseModel):
    id: uuid.UUID
    number: str
    cipher: str
    title: str


class BranchRef(BaseModel):
    id: uuid.UUID
    slug: str
    name: str


class Page(BaseModel):
    id: uuid.UUID
    page_no: int
    url: str
    thumb_url: str | None
    width: int | None
    height: int | None


class DocumentListItem(BaseModel):
    id: uuid.UUID
    cipher: str
    title: str
    summary: str | None
    period_label: str | None
    year_from: int | None
    year_to: int | None
    date_verified: bool
    category: str
    doc_type: str
    file_access: str
    has_digital_copy: bool
    thumb_url: str | None
    fund_number: str
    is_personal_fund: bool
    is_demo: bool
    branch: BranchRef | None
    translation: TranslationInfo


class SearchResponse(BaseModel):
    items: list[DocumentListItem]
    total: int
    page: int
    page_size: int
    pages: int
    fuzzy: bool
    expanded_terms: list[str]


class DocumentCard(BaseModel):
    id: uuid.UUID
    cipher: str
    title: str
    summary: str | None
    historical_note: str | None
    period_label: str | None
    date_from: date | None
    date_to: date | None
    year_from: int | None
    year_to: int | None
    date_verified: bool
    category: str
    doc_type: str
    language: str
    sheets: str | None
    sheets_count: int | None
    storage_location: str | None
    author_org: str | None
    place: str | None
    topic: str | None
    tags: list[str]
    file_access: str
    access_conditions: str | None
    has_digital_copy: bool
    pages: list[Page]  # пусто, если копия закрыта
    fund: Ref
    inventory: Ref
    case: Ref
    branch: BranchRef | None
    is_personal_fund: bool
    is_demo: bool
    translation: TranslationInfo


class ChildItem(BaseModel):
    id: uuid.UUID
    number: str
    cipher: str
    title: str
    year_from: int | None
    year_to: int | None
    count: int | None = None


class HierarchyNode(BaseModel):
    """Фонд / опись / дело с дочерними элементами."""

    level: str  # fund | inventory | case
    id: uuid.UUID
    number: str
    cipher: str
    title: str
    summary: str | None
    historical_note: str | None
    restricted_note: str | None
    year_from: int | None
    year_to: int | None
    is_personal_fund: bool
    is_demo: bool
    branch: BranchRef | None
    parents: list[Ref]
    children: list[ChildItem]
    documents: list[DocumentListItem]
    translation: TranslationInfo


class FacetValue(BaseModel):
    value: str
    count: int
    label: str | None = None


class Facets(BaseModel):
    categories: list[FacetValue]
    doc_types: list[FacetValue]
    branches: list[FacetValue]
    year_min: int | None
    year_max: int | None
    personal_funds: int
