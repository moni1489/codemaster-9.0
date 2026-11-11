"""Общие помощники админ-API."""

from __future__ import annotations

import uuid
from typing import Annotated, Any, TypeVar

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.models.enums import LANGS

Session = Annotated[AsyncSession, Depends(get_session)]
T = TypeVar("T")


async def get_or_404(session: AsyncSession, model: type[T], obj_id: uuid.UUID, what: str = "Объект") -> T:
    obj = await session.get(model, obj_id)
    if obj is None:
        raise HTTPException(404, f"{what} не найден")
    return obj


async def reload(session: AsyncSession, obj: T) -> T:
    """Перечитать объект после commit со связями (selectin) — без ленивой загрузки вне greenlet."""
    from sqlalchemy import select

    model = type(obj)
    stmt = select(model).where(model.id == obj.id).execution_options(populate_existing=True)  # type: ignore[attr-defined]
    return (await session.execute(stmt)).scalar_one()


def upsert_translation(
    obj: Any, model: type[Any], lang: str, values: dict[str, Any], original_lang: str = "ru"
) -> None:
    """Обновить/создать строку перевода; статус: original для языка оригинала, иначе verified (правка человеком)."""
    if lang not in LANGS:
        raise HTTPException(422, f"Неизвестный язык: {lang}")
    existing = next((t for t in obj.translations if t.lang == lang), None)
    status = "original" if lang == original_lang else "verified"
    if existing is None:
        obj.translations.append(model(lang=lang, translation_status=status, **values))
    else:
        for k, v in values.items():
            setattr(existing, k, v)
        if existing.translation_status in ("missing", "machine"):
            existing.translation_status = status


def tr_dict(obj: Any, fields: list[str]) -> dict[str, dict[str, Any]]:
    return {
        t.lang: {"translation_status": t.translation_status, **{f: getattr(t, f) for f in fields}}
        for t in obj.translations
    }


class TransitionIn(BaseModel):
    to: str = Field(pattern="^(draft|review|needs_rework|approved|published|archived)$")
    comment: str | None = Field(default=None, max_length=1000)


class TransitionOut(BaseModel):
    status: str
    version: int
    warning: str | None = None
