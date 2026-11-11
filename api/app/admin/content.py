"""Новости, справочные страницы, FAQ; согласование и версии (ТЗ §5.11, §6.7)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app import audit
from app.admin.common import Session, TransitionIn, TransitionOut, get_or_404, reload, tr_dict, upsert_translation
from app.auth.deps import Principal, current_principal, require
from app.cms.sanitize import clean_html
from app.core.i18n import pick
from app.models import ContentVersion, Faq, FaqGroup, FaqTranslation, News, NewsTranslation, Page, PageTranslation, User
from app.models.cms import NEWS_CATEGORIES
from app.workflow import ENTITIES, edit_status_after, save_version, transition

router = APIRouter(prefix="/api/admin", tags=["admin:content"])
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{2,120}$")


# ---------------- общие схемы ----------------
class ItemSummary(BaseModel):
    entity: str
    id: uuid.UUID
    title: str
    status: str
    updated_at: datetime
    extra: dict[str, Any] = {}


def _title(obj: Any) -> str:
    p = pick(obj.translations, "ru", getattr(obj, "original_lang", "ru"))
    if p is None:
        return str(obj.id)
    tr = p.tr
    return str(getattr(tr, "title", None) or getattr(tr, "question", None) or getattr(tr, "name", None) or obj.id)


# ---------------- новости ----------------
class NewsTrIn(BaseModel):
    title: str = Field(min_length=3, max_length=300)
    lead: str | None = Field(default=None, max_length=1000)
    body: str | None = Field(default=None, max_length=50_000)


class NewsIn(BaseModel):
    slug: str
    category: str = "news"
    published_at: datetime | None = None
    video_url: str | None = Field(default=None, max_length=512, pattern=r"^https://")
    translations: dict[str, NewsTrIn]

    @field_validator("slug")
    @classmethod
    def slug_ok(cls, v: str) -> str:
        if not SLUG.match(v):
            raise ValueError("slug: латиница в нижнем регистре, цифры и дефисы, 3–120 символов")
        return v

    @field_validator("category")
    @classmethod
    def cat_ok(cls, v: str) -> str:
        if v not in NEWS_CATEGORIES:
            raise ValueError(f"категория должна быть одной из: {', '.join(NEWS_CATEGORIES)}")
        return v

    @field_validator("translations")
    @classmethod
    def ru_required(cls, v: dict[str, NewsTrIn]) -> dict[str, NewsTrIn]:
        if "ru" not in v:
            raise ValueError("обязателен заголовок на русском языке (язык оригинала)")
        return v


class NewsPatch(BaseModel):
    category: str | None = None
    published_at: datetime | None = None
    video_url: str | None = Field(default=None, max_length=512, pattern=r"^https://")
    translations: dict[str, NewsTrIn] | None = None


class NewsAdminOut(BaseModel):
    id: uuid.UUID
    slug: str
    category: str
    published_at: datetime | None
    video_url: str | None
    workflow_status: str
    is_demo: bool
    translations: dict[str, dict[str, Any]]


def _news_out(n: News) -> NewsAdminOut:
    return NewsAdminOut(
        id=n.id,
        slug=n.slug,
        category=n.category,
        published_at=n.published_at,
        video_url=n.video_url,
        workflow_status=n.workflow_status,
        is_demo=n.is_demo,
        translations=tr_dict(n, ["title", "lead", "body"]),
    )


def _apply_news_tr(n: News, trs: dict[str, NewsTrIn]) -> None:
    for lang, tr in trs.items():
        upsert_translation(n, NewsTranslation, lang, {"title": tr.title, "lead": tr.lead, "body": clean_html(tr.body)})


@router.get("/news", response_model=list[ItemSummary])
async def admin_news(
    session: Session,
    status: str | None = None,
    p: Principal = Depends(require("content.edit", "content.review", any_of=True)),
) -> list[ItemSummary]:
    stmt = select(News).order_by(News.updated_at.desc())
    if status:
        stmt = stmt.where(News.workflow_status == status)
    return [
        ItemSummary(
            entity="news",
            id=n.id,
            title=_title(n),
            status=n.workflow_status,
            updated_at=n.updated_at,
            extra={"slug": n.slug, "category": n.category, "is_demo": n.is_demo},
        )
        for n in (await session.execute(stmt)).scalars()
    ]


@router.get("/news/{news_id}", response_model=NewsAdminOut)
async def admin_news_get(
    news_id: uuid.UUID, session: Session, p: Principal = Depends(require("content.edit", "content.review", any_of=True))
) -> NewsAdminOut:
    return _news_out(await get_or_404(session, News, news_id, "Новость"))


@router.post("/news", response_model=NewsAdminOut, status_code=201)
async def admin_news_create(
    body: NewsIn, request: Request, session: Session, p: Principal = Depends(require("content.edit"))
) -> NewsAdminOut:
    if (await session.execute(select(News.id).where(News.slug == body.slug))).first():
        raise HTTPException(409, "Новость с таким адресом (slug) уже существует")
    n = News(
        slug=body.slug,
        category=body.category,
        published_at=body.published_at,
        video_url=body.video_url,
        workflow_status="draft",
    )
    _apply_news_tr(n, body.translations)
    session.add(n)
    version = await save_version(session, "news", n, author_id=p.id, comment="Создание")
    audit.record(
        session,
        action="news.create",
        user_id=p.id,
        user_email=p.user.email,
        entity="news",
        entity_id=n.id,
        request=request,
        details={"version": version},
    )
    await session.commit()
    n = await reload(session, n)
    return _news_out(n)


@router.patch("/news/{news_id}", response_model=NewsAdminOut)
async def admin_news_update(
    news_id: uuid.UUID,
    body: NewsPatch,
    request: Request,
    session: Session,
    p: Principal = Depends(require("content.edit")),
) -> NewsAdminOut:
    n = await get_or_404(session, News, news_id, "Новость")
    changes = body.model_dump(exclude_unset=True)
    if "category" in changes and changes["category"] not in NEWS_CATEGORIES:
        raise HTTPException(422, "Неизвестная категория")
    for k in ("category", "published_at", "video_url"):
        if k in changes:
            setattr(n, k, changes[k])
    if body.translations:
        _apply_news_tr(n, body.translations)
    prev = n.workflow_status
    n.workflow_status = edit_status_after(p, prev)
    version = await save_version(session, "news", n, author_id=p.id, comment="Правка")
    audit.record(
        session,
        action="news.update",
        user_id=p.id,
        user_email=p.user.email,
        entity="news",
        entity_id=n.id,
        request=request,
        details={"version": version, "status": f"{prev}->{n.workflow_status}"},
    )
    await session.commit()
    n = await reload(session, n)
    return _news_out(n)


@router.delete("/news/{news_id}", status_code=204, response_model=None)
async def admin_news_delete(
    news_id: uuid.UUID, request: Request, session: Session, p: Principal = Depends(require("content.delete"))
) -> None:
    n = await get_or_404(session, News, news_id, "Новость")
    await save_version(session, "news", n, author_id=p.id, comment="Удаление (последний снимок)")
    audit.record(
        session,
        action="news.delete",
        user_id=p.id,
        user_email=p.user.email,
        entity="news",
        entity_id=n.id,
        request=request,
        details={"slug": n.slug},
    )
    await session.delete(n)
    await session.commit()


# ---------------- справочные страницы ----------------
class PageTrIn(BaseModel):
    title: str = Field(min_length=2, max_length=300)
    body: str | None = Field(default=None, max_length=100_000)
    meta_description: str | None = Field(default=None, max_length=300)


class PagePatch(BaseModel):
    actualized_at: datetime | None = None
    translations: dict[str, PageTrIn]


class PageAdminOut(BaseModel):
    id: uuid.UUID
    slug: str
    section: str
    workflow_status: str
    actualized_at: datetime | None
    is_demo: bool
    translations: dict[str, dict[str, Any]]


def _page_out(pg: Page) -> PageAdminOut:
    return PageAdminOut(
        id=pg.id,
        slug=pg.slug,
        section=pg.section,
        workflow_status=pg.workflow_status,
        actualized_at=pg.actualized_at,
        is_demo=pg.is_demo,
        translations=tr_dict(pg, ["title", "body", "meta_description"]),
    )


@router.get("/pages", response_model=list[ItemSummary])
async def admin_pages(
    session: Session, p: Principal = Depends(require("content.edit", "content.review", any_of=True))
) -> list[ItemSummary]:
    rows = (await session.execute(select(Page).order_by(Page.section, Page.sort_order))).scalars()
    return [
        ItemSummary(
            entity="page",
            id=pg.id,
            title=_title(pg),
            status=pg.workflow_status,
            updated_at=pg.updated_at,
            extra={"slug": pg.slug, "section": pg.section},
        )
        for pg in rows
    ]


@router.get("/pages/{page_id}", response_model=PageAdminOut)
async def admin_page_get(
    page_id: uuid.UUID, session: Session, p: Principal = Depends(require("content.edit", "content.review", any_of=True))
) -> PageAdminOut:
    return _page_out(await get_or_404(session, Page, page_id, "Страница"))


@router.patch("/pages/{page_id}", response_model=PageAdminOut)
async def admin_page_update(
    page_id: uuid.UUID,
    body: PagePatch,
    request: Request,
    session: Session,
    p: Principal = Depends(require("content.edit")),
) -> PageAdminOut:
    pg = await get_or_404(session, Page, page_id, "Страница")
    for lang, tr in body.translations.items():
        upsert_translation(
            pg,
            PageTranslation,
            lang,
            {"title": tr.title, "body": clean_html(tr.body), "meta_description": tr.meta_description},
        )
    if body.actualized_at is not None:
        pg.actualized_at = body.actualized_at
    prev = pg.workflow_status
    pg.workflow_status = edit_status_after(p, prev)
    version = await save_version(session, "page", pg, author_id=p.id, comment="Правка")
    audit.record(
        session,
        action="page.update",
        user_id=p.id,
        user_email=p.user.email,
        entity="page",
        entity_id=pg.id,
        request=request,
        details={"version": version, "status": f"{prev}->{pg.workflow_status}"},
    )
    await session.commit()
    pg = await reload(session, pg)
    return _page_out(pg)


# ---------------- FAQ ----------------
class FaqTrIn(BaseModel):
    question: str = Field(min_length=5, max_length=500)
    answer: str = Field(min_length=2, max_length=5000)


class FaqIn(BaseModel):
    group_id: uuid.UUID
    sort_order: int = 0
    translations: dict[str, FaqTrIn]


class FaqAdminOut(BaseModel):
    id: uuid.UUID
    group_id: uuid.UUID
    group: str
    sort_order: int
    workflow_status: str
    translations: dict[str, dict[str, Any]]


@router.get("/faq", response_model=list[FaqAdminOut])
async def admin_faq(
    session: Session, p: Principal = Depends(require("content.edit", "content.review", any_of=True))
) -> list[FaqAdminOut]:
    groups = {g.id: g.slug for g in (await session.execute(select(FaqGroup))).scalars()}
    rows = (await session.execute(select(Faq).order_by(Faq.group_id, Faq.sort_order))).scalars()
    return [
        FaqAdminOut(
            id=f.id,
            group_id=f.group_id,
            group=groups.get(f.group_id, ""),
            sort_order=f.sort_order,
            workflow_status=f.workflow_status,
            translations=tr_dict(f, ["question", "answer"]),
        )
        for f in rows
    ]


@router.post("/faq", response_model=FaqAdminOut, status_code=201)
async def admin_faq_create(
    body: FaqIn, request: Request, session: Session, p: Principal = Depends(require("content.edit"))
) -> FaqAdminOut:
    group = await get_or_404(session, FaqGroup, body.group_id, "Группа FAQ")
    if "ru" not in body.translations:
        raise HTTPException(422, "Обязателен вопрос и ответ на русском языке")
    f = Faq(group_id=group.id, sort_order=body.sort_order, workflow_status="draft")
    for lang, tr in body.translations.items():
        upsert_translation(f, FaqTranslation, lang, tr.model_dump())
    session.add(f)
    await save_version(session, "faq", f, author_id=p.id, comment="Создание")
    audit.record(
        session,
        action="faq.create",
        user_id=p.id,
        user_email=p.user.email,
        entity="faq",
        entity_id=f.id,
        request=request,
    )
    await session.commit()
    f = await reload(session, f)
    return FaqAdminOut(
        id=f.id,
        group_id=f.group_id,
        group=group.slug,
        sort_order=f.sort_order,
        workflow_status=f.workflow_status,
        translations=tr_dict(f, ["question", "answer"]),
    )


@router.delete("/faq/{faq_id}", status_code=204, response_model=None)
async def admin_faq_delete(
    faq_id: uuid.UUID, request: Request, session: Session, p: Principal = Depends(require("content.delete"))
) -> None:
    f = await get_or_404(session, Faq, faq_id, "Вопрос")
    audit.record(
        session,
        action="faq.delete",
        user_id=p.id,
        user_email=p.user.email,
        entity="faq",
        entity_id=f.id,
        request=request,
    )
    await session.delete(f)
    await session.commit()


# ---------------- согласование ----------------
@router.post("/workflow/{entity}/{obj_id}", response_model=TransitionOut)
async def do_transition(
    entity: str,
    obj_id: uuid.UUID,
    body: TransitionIn,
    request: Request,
    session: Session,
    p: Principal = Depends(current_principal),
) -> TransitionOut:
    model = ENTITIES.get(entity)
    if model is None:
        raise HTTPException(404, "Неизвестный тип материала")
    obj = await get_or_404(session, model, obj_id)
    result = await transition(session, p, request, entity, obj, body.to, body.comment)
    await session.commit()
    return TransitionOut(status=result.status, version=result.version, warning=result.warning)


class VersionOut(BaseModel):
    version: int
    status: str
    changed_at: datetime
    author: str | None
    reviewer: str | None
    comment: str | None


@router.get("/workflow/{entity}/{obj_id}/versions", response_model=list[VersionOut])
async def versions(
    entity: str, obj_id: uuid.UUID, session: Session, p: Principal = Depends(current_principal)
) -> list[VersionOut]:
    rows = (
        (
            await session.execute(
                select(ContentVersion)
                .where(ContentVersion.entity == entity, ContentVersion.entity_id == obj_id)
                .order_by(ContentVersion.version.desc())
            )
        )
        .scalars()
        .all()
    )
    ids = {i for r in rows for i in (r.author_id, r.reviewer_id) if i}
    users = (
        {u.id: u.email for u in (await session.execute(select(User).where(User.id.in_(ids)))).scalars()} if ids else {}
    )
    return [
        VersionOut(
            version=r.version,
            status=r.status,
            changed_at=r.changed_at,
            author=users.get(r.author_id) if r.author_id else None,
            reviewer=users.get(r.reviewer_id) if r.reviewer_id else None,
            comment=r.comment,
        )
        for r in rows
    ]


@router.get("/review-queue", response_model=list[ItemSummary])
async def review_queue(session: Session, p: Principal = Depends(require("content.review"))) -> list[ItemSummary]:
    out: list[ItemSummary] = []
    for name, model in ENTITIES.items():
        rows = (await session.execute(select(model).where(model.workflow_status.in_(("review", "approved"))))).scalars()
        out += [
            ItemSummary(entity=name, id=o.id, title=_title(o), status=o.workflow_status, updated_at=o.updated_at)
            for o in rows
        ]
    return sorted(out, key=lambda i: i.updated_at, reverse=True)
