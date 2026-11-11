"""Каталог: фонд → опись → дело (таблица files) → документ; цифровые файлы.

Две независимые оси доступа (Д §3.1): description_status — публикация описания,
file_access — доступность цифровой копии. Плюс редакционный workflow_status.
"""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, TranslationMixin, WorkflowMixin, workflow_checks
from app.models.enums import (
    CATEGORIES,
    DESCRIPTION_STATUSES,
    DIGITAL_FILE_KINDS,
    DOC_TYPES,
    FILE_ACCESS,
    check_in,
)


def _desc_check() -> CheckConstraint:
    return CheckConstraint(check_in("description_status", DESCRIPTION_STATUSES), name="description_status")


class Fund(IdMixin, TimestampMixin, WorkflowMixin, Base):
    __tablename__ = "funds"
    __table_args__ = (_desc_check(), *workflow_checks())

    number: Mapped[str] = mapped_column(String(32), unique=True)  # «Р-101», «Л-15»
    cipher: Mapped[str] = mapped_column(String(128), unique=True)
    year_from: Mapped[int | None] = mapped_column(Integer)
    year_to: Mapped[int | None] = mapped_column(Integer)
    is_personal_fund: Mapped[bool] = mapped_column(Boolean, default=False)
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    description_status: Mapped[str] = mapped_column(String(8), default="review")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    translations: Mapped[list[FundTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class FundTranslation(TranslationMixin, Base):
    __tablename__ = "fund_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("funds.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    historical_note: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    restricted_note: Mapped[str | None] = mapped_column(Text)


class Inventory(IdMixin, TimestampMixin, WorkflowMixin, Base):
    __tablename__ = "inventories"
    __table_args__ = (
        UniqueConstraint("fund_id", "number", name="fund_number"),
        _desc_check(),
        *workflow_checks(),
    )

    fund_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("funds.id", ondelete="RESTRICT"))
    number: Mapped[str] = mapped_column(String(32))
    cipher: Mapped[str] = mapped_column(String(128), unique=True)
    year_from: Mapped[int | None] = mapped_column(Integer)
    year_to: Mapped[int | None] = mapped_column(Integer)
    description_status: Mapped[str] = mapped_column(String(8), default="review")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    translations: Mapped[list[InventoryTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class InventoryTranslation(TranslationMixin, Base):
    __tablename__ = "inventory_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventories.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)


class ArchiveCase(IdMixin, TimestampMixin, WorkflowMixin, Base):
    """Архивное дело. Таблица называется files по терминологии постановки."""

    __tablename__ = "files"
    __table_args__ = (
        UniqueConstraint("inventory_id", "number", name="inventory_number"),
        _desc_check(),
        *workflow_checks(),
    )

    inventory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventories.id", ondelete="RESTRICT"))
    number: Mapped[str] = mapped_column(String(32))
    cipher: Mapped[str] = mapped_column(String(128), unique=True)
    year_from: Mapped[int | None] = mapped_column(Integer)
    year_to: Mapped[int | None] = mapped_column(Integer)
    sheets_count: Mapped[int | None] = mapped_column(Integer)
    description_status: Mapped[str] = mapped_column(String(8), default="review")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    translations: Mapped[list[CaseTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class CaseTranslation(TranslationMixin, Base):
    __tablename__ = "file_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)


class Document(IdMixin, TimestampMixin, WorkflowMixin, Base):
    __tablename__ = "documents"
    __table_args__ = (
        _desc_check(),
        CheckConstraint(check_in("file_access", FILE_ACCESS), name="file_access"),
        CheckConstraint(check_in("category", CATEGORIES), name="category"),
        CheckConstraint(check_in("doc_type", DOC_TYPES), name="doc_type"),
        CheckConstraint("date_to IS NULL OR date_from IS NULL OR date_to >= date_from", name="date_order"),
        Index("ix_documents_years", "year_from", "year_to"),
        *workflow_checks(),
    )

    case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("files.id", ondelete="RESTRICT"), index=True)
    # денормализация для фильтров; поддерживается сервисом каталога
    inventory_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("inventories.id", ondelete="RESTRICT"))
    fund_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("funds.id", ondelete="RESTRICT"), index=True)
    fund_number: Mapped[str] = mapped_column(String(32), index=True)
    inventory_number: Mapped[str] = mapped_column(String(32))
    case_number: Mapped[str] = mapped_column(String(32))

    cipher: Mapped[str] = mapped_column(String(160), unique=True)
    sheets: Mapped[str | None] = mapped_column(String(32))  # «л. 3–7»
    date_from: Mapped[date | None] = mapped_column(Date)
    date_to: Mapped[date | None] = mapped_column(Date)
    year_from: Mapped[int | None] = mapped_column(Integer)
    year_to: Mapped[int | None] = mapped_column(Integer)
    date_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    category: Mapped[str] = mapped_column(String(16))
    doc_type: Mapped[str] = mapped_column(String(16))
    language: Mapped[str] = mapped_column(String(32), default="ru")  # язык самого документа
    sheets_count: Mapped[int | None] = mapped_column(Integer)
    storage_location: Mapped[str | None] = mapped_column(String(255))
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    tags: Mapped[list[str]] = mapped_column(default=list)
    is_personal_fund: Mapped[bool] = mapped_column(Boolean, default=False)

    description_status: Mapped[str] = mapped_column(String(8), default="review")
    file_access: Mapped[str] = mapped_column(String(12), default="closed")
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    translations: Mapped[list[DocumentTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class DocumentTranslation(TranslationMixin, Base):
    __tablename__ = "document_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    historical_note: Mapped[str | None] = mapped_column(Text)
    period_label: Mapped[str | None] = mapped_column(String(128))
    author_org: Mapped[str | None] = mapped_column(Text)
    place: Mapped[str | None] = mapped_column(String(255))
    topic: Mapped[str | None] = mapped_column(String(255))
    access_conditions: Mapped[str | None] = mapped_column(Text)


class DigitalFile(IdMixin, TimestampMixin, Base):
    """Мастер-копия (не отдаётся публично) и производные облегчённые копии (WebP)."""

    __tablename__ = "digital_files"
    __table_args__ = (
        CheckConstraint(check_in("kind", DIGITAL_FILE_KINDS), name="kind"),
        CheckConstraint("kind = 'master' OR parent_id IS NOT NULL", name="derived_has_parent"),
    )

    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    parent_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("digital_files.id", ondelete="CASCADE"))
    kind: Mapped[str] = mapped_column(String(8))
    page_no: Mapped[int] = mapped_column(Integer, default=1)
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    original_filename: Mapped[str | None] = mapped_column(String(255))
    mime: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    provenance: Mapped[str | None] = mapped_column(Text)
    rights_note: Mapped[str | None] = mapped_column(Text)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
