"""Публичные DTO: филиалы, памятные даты."""

from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.catalog.schemas import TranslationInfo


class BranchOut(BaseModel):
    id: uuid.UUID
    slug: str
    type: str
    name: str
    short_name: str
    locality: str
    address: str
    hours: str | None
    hours_verified: bool
    director: str | None
    phone: str | None
    phones_extra: dict[str, str] | None
    email: str | None
    lat: float | None
    lon: float | None
    coords_verified: bool
    photo_url: str | None
    description: str | None
    translation: TranslationInfo


class MemorialDateOut(BaseModel):
    id: uuid.UUID
    year: int
    month: int | None
    day: int | None
    date_label: str | None
    title: str
    source: str | None
    translation: TranslationInfo


class TodayOut(BaseModel):
    date: str  # MM-DD
    exact: bool  # True — события ровно на эту дату; False — ближайшие в этом месяце
    items: list[MemorialDateOut]
