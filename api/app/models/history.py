"""Цифровая история региона: коллекции, персоналии, события-хронология; онлайн-выставки."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, TranslationMixin, WorkflowMixin, workflow_checks


class Collection(IdMixin, TimestampMixin, WorkflowMixin, Base):
    __tablename__ = "collections"
    __table_args__ = workflow_checks()

    slug: Mapped[str] = mapped_column(String(128), unique=True)
    topic: Mapped[str | None] = mapped_column(String(64))
    cover_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("digital_files.id", ondelete="SET NULL"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    translations: Mapped[list[CollectionTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    items: Mapped[list[CollectionItem]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="CollectionItem.sort_order"
    )


class CollectionTranslation(TranslationMixin, Base):
    __tablename__ = "collection_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    editorial_note: Mapped[str | None] = mapped_column(Text)  # редакционное пояснение, отделено от фактов


class CollectionItem(IdMixin, Base):
    __tablename__ = "collection_items"

    collection_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"))
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    note: Mapped[str | None] = mapped_column(Text)


class Person(IdMixin, TimestampMixin, WorkflowMixin, Base):
    __tablename__ = "persons"
    __table_args__ = workflow_checks()

    slug: Mapped[str] = mapped_column(String(128), unique=True)
    birth_label: Mapped[str | None] = mapped_column(String(64))
    death_label: Mapped[str | None] = mapped_column(String(64))
    dates_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    portrait_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("digital_files.id", ondelete="SET NULL"))
    is_fictional: Mapped[bool] = mapped_column(Boolean, default=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    translations: Mapped[list[PersonTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class PersonTranslation(TranslationMixin, Base):
    __tablename__ = "person_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("persons.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    role_line: Mapped[str | None] = mapped_column(String(255))
    bio: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(Text)


class Event(IdMixin, TimestampMixin, WorkflowMixin, Base):
    __tablename__ = "events"
    __table_args__ = workflow_checks()

    year: Mapped[int] = mapped_column(Integer, index=True)
    year_to: Mapped[int | None] = mapped_column(Integer)
    date_verified: Mapped[bool] = mapped_column(Boolean, default=True)
    topic: Mapped[str] = mapped_column(String(64))
    is_editorial: Mapped[bool] = mapped_column(Boolean, default=False)  # редакционная интерпретация
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    collection_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("collections.id", ondelete="SET NULL"))
    person_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("persons.id", ondelete="SET NULL"))
    translations: Mapped[list[EventTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class EventTranslation(TranslationMixin, Base):
    __tablename__ = "event_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("events.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    place: Mapped[str | None] = mapped_column(String(255))
    source: Mapped[str | None] = mapped_column(Text)


class Exhibition(IdMixin, TimestampMixin, WorkflowMixin, Base):
    __tablename__ = "exhibitions"
    __table_args__ = workflow_checks()

    slug: Mapped[str] = mapped_column(String(128), unique=True)
    topic: Mapped[str | None] = mapped_column(String(64))
    period_from: Mapped[int | None] = mapped_column(Integer)
    period_to: Mapped[int | None] = mapped_column(Integer)
    cover_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("digital_files.id", ondelete="SET NULL"))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    translations: Mapped[list[ExhibitionTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")
    exhibits: Mapped[list[Exhibit]] = relationship(
        lazy="selectin", cascade="all, delete-orphan", order_by="Exhibit.sort_order"
    )


class ExhibitionTranslation(TranslationMixin, Base):
    __tablename__ = "exhibition_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exhibitions.id", ondelete="CASCADE"), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)


class Exhibit(IdMixin, TimestampMixin, Base):
    __tablename__ = "exhibits"

    exhibition_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exhibitions.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("documents.id", ondelete="SET NULL"))
    image_file_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("digital_files.id", ondelete="SET NULL"))
    video_url: Mapped[str | None] = mapped_column(String(512))
    source_text: Mapped[str | None] = mapped_column(Text)  # источник прямо в карточке экспоната (Д §3.2)
    rights_note: Mapped[str | None] = mapped_column(Text)
    translations: Mapped[list[ExhibitTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class ExhibitTranslation(TranslationMixin, Base):
    __tablename__ = "exhibit_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("exhibits.id", ondelete="CASCADE"), primary_key=True)
    caption: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
