"""Базовые классы ORM: суррогатный UUID, метки времени, переводы."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, MetaData, String, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from app.models.enums import LANGS, TRANSLATION_STATUSES, WORKFLOW_STATUSES, check_in

NAMING = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)
    type_annotation_map = {dict[str, Any]: JSONB, list[dict[str, Any]]: JSONB, list[str]: ARRAY(String)}  # noqa: RUF012


class IdMixin:
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class WorkflowMixin:
    """Редакционный статус (ТЗ §6.7). Публично видно только `published`."""

    workflow_status: Mapped[str] = mapped_column(String(16), default="draft", server_default="draft")
    original_lang: Mapped[str] = mapped_column(String(2), default="ru", server_default="ru")


def workflow_checks() -> tuple[CheckConstraint, ...]:
    """CHECK-ограничения для моделей с WorkflowMixin (новые объекты на каждую таблицу)."""
    return (
        CheckConstraint(check_in("workflow_status", WORKFLOW_STATUSES), name="workflow_status"),
        CheckConstraint(check_in("original_lang", LANGS), name="original_lang"),
    )


class TranslationMixin:
    """Строка перевода: (entity_id, lang) — PK задаётся в наследнике вместе с FK."""

    lang: Mapped[str] = mapped_column(String(2), primary_key=True)
    translation_status: Mapped[str] = mapped_column(String(10), default="original")

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Any, ...]:
        return (
            CheckConstraint(check_in("lang", LANGS), name="lang"),
            CheckConstraint(check_in("translation_status", TRANSLATION_STATUSES), name="translation_status"),
        )
