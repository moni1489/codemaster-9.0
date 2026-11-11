"""Единая точка правил публичного доступа к каталогу (D-004). Deny by default.

Запись видна публично ⇔ она и вся цепочка предков: description_status='public' И workflow_status='published'.
Цифровая копия выдаётся ⇔ документ виден И file_access='open' И файл — производная копия (не мастер).
"""

from __future__ import annotations

from sqlalchemy import ColumnElement, and_, exists, select

from app.models import ArchiveCase, DigitalFile, Document, Fund, Inventory

PUBLIC_DESCRIPTION = "public"
PUBLISHED = "published"
OPEN = "open"
PUBLIC_FILE_KINDS = ("view", "thumb")


def _visible(model: type[Fund] | type[Inventory] | type[ArchiveCase] | type[Document]) -> ColumnElement[bool]:
    return and_(model.description_status == PUBLIC_DESCRIPTION, model.workflow_status == PUBLISHED)


def fund_visible() -> ColumnElement[bool]:
    return _visible(Fund)


def inventory_visible() -> ColumnElement[bool]:
    return and_(
        _visible(Inventory),
        exists(select(Fund.id).where(Fund.id == Inventory.fund_id, fund_visible())),
    )


def case_visible() -> ColumnElement[bool]:
    return and_(
        _visible(ArchiveCase),
        exists(select(Inventory.id).where(Inventory.id == ArchiveCase.inventory_id, inventory_visible())),
    )


def document_visible() -> ColumnElement[bool]:
    """Предикат для запросов по Document. Предки проверяются коррелированными подзапросами."""
    return and_(
        _visible(Document),
        exists(select(ArchiveCase.id).where(ArchiveCase.id == Document.case_id, case_visible())),
    )


def document_file_open() -> ColumnElement[bool]:
    return and_(document_visible(), Document.file_access == OPEN)


def is_file_public_kind(f: DigitalFile) -> bool:
    return f.kind in PUBLIC_FILE_KINDS
