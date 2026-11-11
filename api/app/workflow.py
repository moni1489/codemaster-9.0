"""Согласование публикаций (ТЗ §6.7, Д §3.5) и версии контента.

Статусы: draft → review → (needs_rework | approved) → published → archived.
Каждый переход и каждая правка сохраняют снимок в content_versions (автор, согласующий, дата, комментарий)
и запись в audit_log. Переход не меняет доступ к цифровым копиям (file_access) — это отдельное право.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import func, inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.auth.deps import Principal, deny
from app.models import (
    ArchiveCase,
    Collection,
    ContentVersion,
    Document,
    Event,
    Exhibition,
    Faq,
    Fund,
    Inventory,
    News,
    Page,
    Person,
)
from app.search.postgres import get_search_backend

ENTITIES: dict[str, type[Any]] = {
    "news": News,
    "page": Page,
    "faq": Faq,
    "document": Document,
    "fund": Fund,
    "inventory": Inventory,
    "case": ArchiveCase,
    "exhibition": Exhibition,
    "collection": Collection,
    "person": Person,
    "event": Event,
}

# (из, в) → требуемые права (все)
TRANSITIONS: dict[tuple[str, str], tuple[str, ...]] = {
    ("draft", "review"): ("content.submit",),
    ("needs_rework", "review"): ("content.submit",),
    ("review", "needs_rework"): ("content.review",),
    ("approved", "needs_rework"): ("content.review",),
    ("review", "approved"): ("content.review",),
    ("approved", "published"): ("content.publish",),
    ("review", "published"): ("content.review", "content.publish"),  # «одобрить и опубликовать»
    ("published", "draft"): ("content.publish",),  # снять с публикации
    ("published", "archived"): ("content.publish",),
    ("archived", "draft"): ("content.publish",),
}
REVIEW_TARGETS = {"approved", "published", "needs_rework"}


def _jsonable(v: Any) -> Any:
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, datetime | date):
        return v.isoformat()
    if isinstance(v, list):
        return [_jsonable(x) for x in v]
    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    return v


def snapshot(obj: Any) -> dict[str, Any]:
    mapper = inspect(type(obj))
    data = {c.key: _jsonable(getattr(obj, c.key)) for c in mapper.column_attrs}
    trs = getattr(obj, "translations", None)
    if trs is not None:
        data["translations"] = [
            {c.key: _jsonable(getattr(t, c.key)) for c in inspect(type(t)).column_attrs if c.key != "entity_id"}
            for t in trs
        ]
    return data


async def _last_version(session: AsyncSession, entity: str, entity_id: uuid.UUID) -> ContentVersion | None:
    return (
        await session.execute(
            select(ContentVersion)
            .where(ContentVersion.entity == entity, ContentVersion.entity_id == entity_id)
            .order_by(ContentVersion.version.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def save_version(
    session: AsyncSession,
    entity: str,
    obj: Any,
    *,
    author_id: uuid.UUID | None,
    reviewer_id: uuid.UUID | None = None,
    comment: str | None = None,
) -> int:
    await session.flush()
    current = (
        await session.execute(
            select(func.coalesce(func.max(ContentVersion.version), 0)).where(
                ContentVersion.entity == entity, ContentVersion.entity_id == obj.id
            )
        )
    ).scalar_one()
    version = int(current) + 1
    # после flush серверные значения (updated_at и т.п.) устаревают — перечитываем колонки асинхронно
    await session.refresh(obj, attribute_names=[c.key for c in inspect(type(obj)).column_attrs])
    session.add(
        ContentVersion(
            entity=entity,
            entity_id=obj.id,
            version=version,
            payload=snapshot(obj),
            status=obj.workflow_status,
            author_id=author_id,
            reviewer_id=reviewer_id,
            comment=comment,
        )
    )
    return version


@dataclass
class TransitionResult:
    status: str
    version: int
    warning: str | None = None


CATALOG_ENTITIES = {"document", "fund", "inventory", "case"}
_CHILD_FK = {"fund": Document.fund_id, "inventory": Document.inventory_id, "case": Document.case_id}


async def after_status_change(session: AsyncSession, entity: str, obj: Any) -> None:
    """Публичный индекс следует за статусом: документ и все документы под фондом/описью/делом."""
    if entity not in CATALOG_ENTITIES:
        return
    await session.flush()
    backend = get_search_backend()
    if entity == "document":
        await backend.index_document(session, obj.id)
        return
    for doc_id in (await session.execute(select(Document.id).where(_CHILD_FK[entity] == obj.id))).scalars():
        await backend.index_document(session, doc_id)


async def transition(
    session: AsyncSession,
    principal: Principal,
    request: Request,
    entity: str,
    obj: Any,
    to: str,
    comment: str | None,
) -> TransitionResult:
    src = obj.workflow_status
    required = TRANSITIONS.get((src, to))
    if required is None:
        raise HTTPException(409, f"Переход «{src} → {to}» недопустим")
    if not all(principal.has(p) for p in required):
        await deny(principal, request, action=f"workflow.{src}->{to}", entity=entity, entity_id=obj.id)
    if to in REVIEW_TARGETS and "superadmin" not in principal.roles:
        last = await _last_version(session, entity, obj.id)
        if last and last.status == "review" and last.author_id == principal.id:
            await deny(
                principal,
                request,
                action=f"workflow.{src}->{to}",
                entity=entity,
                entity_id=obj.id,
                message="Нельзя согласовать собственный материал (принцип четырёх глаз)",
            )
    warning = None
    obj.workflow_status = to
    if entity == "news" and to == "published" and obj.published_at is None:
        obj.published_at = datetime.now(UTC)
    if entity in CATALOG_ENTITIES and to == "published":
        # одобренное модератором описание становится публичным; «Не публиковать» не снимается автоматически
        if obj.description_status == "review":
            obj.description_status = "public"
        elif obj.description_status == "hidden":
            warning = "Описание помечено «Не публиковать» — документ не появится на сайте, пока статус не изменён"
    is_review = to in REVIEW_TARGETS
    version = await save_version(
        session,
        entity,
        obj,
        author_id=None if is_review else principal.id,
        reviewer_id=principal.id if is_review else None,
        comment=comment,
    )
    audit.record(
        session,
        action=f"workflow.{src}->{to}",
        user_id=principal.id,
        user_email=principal.user.email,
        entity=entity,
        entity_id=obj.id,
        request=request,
        details={"version": version, "comment": comment},
    )
    await after_status_change(session, entity, obj)
    return TransitionResult(status=to, version=version, warning=warning)


def edit_status_after(principal: Principal, current: str) -> str:
    """Правка опубликованного/согласованного материала без права публикации возвращает его на проверку."""
    if current in {"review", "approved", "published"} and not principal.has("content.publish"):
        return "review"
    return current
