"""Новости, CMS-страницы, FAQ, памятные даты, отзывы."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, TranslationMixin, WorkflowMixin, workflow_checks
from app.models.enums import check_in

NEWS_CATEGORIES = ("news", "exhibition", "conference", "event", "research", "branch")


class News(IdMixin, TimestampMixin, WorkflowMixin, Base):
    __tablename__ = "news"
    __table_args__ = (
        CheckConstraint(check_in("category", NEWS_CATEGORIES), name="category"),
        *workflow_checks(),
    )

    slug: Mapped[str] = mapped_column(String(128), unique=True)
    category: Mapped[str] = mapped_column(String(16), default="news")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    cover_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("digital_files.id", ondelete="SET NULL"))
    video_url: Mapped[str | None] = mapped_column(String(512))
    branch_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("branches.id", ondelete="SET NULL"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    translations: Mapped[list[NewsTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class NewsTranslation(TranslationMixin, Base):
    __tablename__ = "news_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("news.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    lead: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)  # санитизированный HTML


class Page(IdMixin, TimestampMixin, WorkflowMixin, Base):
    """Справочная страница (об архиве, госуслуга, платные услуги, антикоррупция, читальный зал…)."""

    __tablename__ = "pages"
    __table_args__ = workflow_checks()

    slug: Mapped[str] = mapped_column(String(128), unique=True)
    section: Mapped[str] = mapped_column(String(32), default="about")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    actualized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # [{"title": {...}, "url": "...", "external": true, "kind": "pdf|link"}]
    attachments: Mapped[list[dict[str, Any]] | None] = mapped_column(default=None)
    data: Mapped[dict[str, Any] | None]  # структурированные блоки (прейскурант и т.п.)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)

    translations: Mapped[list[PageTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class PageTranslation(TranslationMixin, Base):
    __tablename__ = "page_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("pages.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)  # санитизированный HTML
    meta_description: Mapped[str | None] = mapped_column(String(300))


class FaqGroup(IdMixin, TimestampMixin, Base):
    __tablename__ = "faq_groups"

    slug: Mapped[str] = mapped_column(String(64), unique=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    translations: Mapped[list[FaqGroupTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class FaqGroupTranslation(TranslationMixin, Base):
    __tablename__ = "faq_group_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("faq_groups.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(String(255))


class Faq(IdMixin, TimestampMixin, WorkflowMixin, Base):
    __tablename__ = "faq"
    __table_args__ = workflow_checks()

    group_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("faq_groups.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    translations: Mapped[list[FaqTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class FaqTranslation(TranslationMixin, Base):
    __tablename__ = "faq_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("faq.id", ondelete="CASCADE"), primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)


class MemorialDate(IdMixin, TimestampMixin, Base):
    __tablename__ = "memorial_dates"
    __table_args__ = (
        CheckConstraint("month IS NULL OR month BETWEEN 1 AND 12", name="month"),
        CheckConstraint("day IS NULL OR day BETWEEN 1 AND 31", name="day"),
    )

    ext_id: Mapped[str] = mapped_column(String(32), unique=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    month: Mapped[int | None] = mapped_column(Integer)
    day: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(255))
    translations: Mapped[list[MemorialDateTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class MemorialDateTranslation(TranslationMixin, Base):
    __tablename__ = "memorial_date_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("memorial_dates.id", ondelete="CASCADE"), primary_key=True)
    date_label: Mapped[str | None] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(Text)


class Feedback(IdMixin, Base):
    """Отзыв/предложение по работе сайта. НЕ официальное обращение. ПДн — только опциональный email."""

    __tablename__ = "feedback"
    __table_args__ = (CheckConstraint("email IS NULL OR consent", name="email_requires_consent"),)

    message: Mapped[str] = mapped_column(Text)
    page: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    consent: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
