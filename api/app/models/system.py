"""Версии контента, журнал действий, журнал поиска, синонимы, поисковый индекс."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import WORKFLOW_STATUSES, check_in


class ContentVersion(Base):
    __tablename__ = "content_versions"
    __table_args__ = (
        CheckConstraint(check_in("status", WORKFLOW_STATUSES), name="status"),
        Index("ix_content_versions_entity", "entity", "entity_id", "version", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    entity: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[uuid.UUID] = mapped_column()
    version: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict[str, Any]]
    status: Mapped[str] = mapped_column(String(16))
    author_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    comment: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    """Журнал действий админки (ТЗ §6.8, Д §3.5). Без паролей, токенов и содержимого документов."""

    __tablename__ = "audit_log"
    __table_args__ = (CheckConstraint("result IN ('success', 'denied', 'error')", name="result"),)

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    user_email: Mapped[str | None] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(64))
    entity: Mapped[str | None] = mapped_column(String(32))
    entity_id: Mapped[str | None] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(8))
    ip: Mapped[str | None] = mapped_column(String(64))
    details: Mapped[dict[str, Any] | None]


class SearchLog(Base):
    """Обезличенный журнал запросов для аналитики: без IP, user-agent, cookie."""

    __tablename__ = "search_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    query: Mapped[str] = mapped_column(String(300))
    lang: Mapped[str] = mapped_column(String(2))
    source: Mapped[str] = mapped_column(String(16), default="catalog")
    results_count: Mapped[int] = mapped_column(Integer)
    ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)


class Synonym(Base):
    """Группы синонимов/вариантов написания (Өскемен ↔ Усть-Каменогорск ↔ Oskemen …)."""

    __tablename__ = "synonyms"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    group_key: Mapped[str] = mapped_column(String(64), index=True)
    term: Mapped[str] = mapped_column(String(128), unique=True)


class SearchIndex(Base):
    """Полнотекстовый индекс. Содержит ТОЛЬКО публично видимые документы (D-004, D-006)."""

    __tablename__ = "search_index"
    __table_args__ = (
        Index("ix_search_index_tsv", "tsv", postgresql_using="gin"),
        Index(
            "ix_search_index_trgm",
            "search_text",
            postgresql_using="gin",
            postgresql_ops={"search_text": "gin_trgm_ops"},
        ),
    )

    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    tsv: Mapped[Any] = mapped_column(TSVECTOR)
    search_text: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
