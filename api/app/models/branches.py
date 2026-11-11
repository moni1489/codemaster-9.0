"""Главное здание и филиалы (ТЗ §5.5, §6.4)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import Boolean, CheckConstraint, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, IdMixin, TimestampMixin, TranslationMixin
from app.models.enums import BRANCH_TYPES, check_in


class Branch(IdMixin, TimestampMixin, Base):
    __tablename__ = "branches"
    __table_args__ = (
        CheckConstraint(check_in("type", BRANCH_TYPES), name="type"),
        CheckConstraint("lat IS NULL OR (lat BETWEEN -90 AND 90)", name="lat"),
        CheckConstraint("lon IS NULL OR (lon BETWEEN -180 AND 180)", name="lon"),
    )

    slug: Mapped[str] = mapped_column(String(64), unique=True)
    type: Mapped[str] = mapped_column(String(8))
    official_name: Mapped[str | None] = mapped_column(Text)
    director: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    phones_extra: Mapped[dict[str, Any] | None]
    email: Mapped[str | None] = mapped_column(String(255))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    coords_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    hours_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    visible: Mapped[bool] = mapped_column(Boolean, default=True)
    photo_file_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("digital_files.id", ondelete="SET NULL", use_alter=True)
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    source: Mapped[str | None] = mapped_column(String(255))

    translations: Mapped[list[BranchTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class BranchTranslation(TranslationMixin, Base):
    __tablename__ = "branch_translations"

    entity_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("branches.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(Text)
    short_name: Mapped[str] = mapped_column(String(255))
    locality: Mapped[str] = mapped_column(String(255))
    address: Mapped[str] = mapped_column(Text)
    hours: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
