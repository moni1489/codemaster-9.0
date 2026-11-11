"""Публичные DTO справочных страниц, новостей, FAQ и отзывов."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.catalog.schemas import TranslationInfo


class Attachment(BaseModel):
    title: str
    url: str
    kind: str  # pdf | link
    external: bool
    lang: str | None = None
    verified: bool = True  # ссылка подтверждена заказчиком


class PageOut(BaseModel):
    slug: str
    section: str
    title: str
    body: str | None  # санитизированный HTML
    meta_description: str | None
    actualized_at: datetime | None
    attachments: list[Attachment]
    data: dict[str, Any] | None
    is_demo: bool
    translation: TranslationInfo


class PageLink(BaseModel):
    slug: str
    section: str
    title: str


class NewsItem(BaseModel):
    id: uuid.UUID
    slug: str
    category: str
    published_at: datetime | None
    title: str
    lead: str | None
    cover_url: str | None
    is_demo: bool
    translation: TranslationInfo


class NewsList(BaseModel):
    items: list[NewsItem]
    total: int
    page: int
    pages: int


class NewsOut(NewsItem):
    body: str | None
    video_url: str | None
    related: list[NewsItem]


class FaqItem(BaseModel):
    id: uuid.UUID
    question: str
    answer: str
    translation: TranslationInfo


class FaqGroupOut(BaseModel):
    slug: str
    title: str
    items: list[FaqItem]


class FeedbackIn(BaseModel):
    """Отзыв о работе сайта. Не является официальным обращением; ПДн — только опциональный email с согласием."""

    message: str = Field(min_length=10, max_length=2000)
    page: str | None = Field(default=None, max_length=255)
    email: EmailStr | None = None
    consent: bool = False

    @field_validator("message")
    @classmethod
    def strip_message(cls, v: str) -> str:
        return v.strip()

    @model_validator(mode="after")
    def email_needs_consent(self) -> FeedbackIn:
        if self.email and not self.consent:
            raise ValueError("Для указания e-mail нужно согласие на обработку персональных данных")
        return self


class FeedbackAck(BaseModel):
    ok: bool
    notice: str
