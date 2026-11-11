"""Публичный API справочных страниц, новостей, FAQ, отзывов и официальных документов.

Видно только опубликованное (workflow_status='published'). Отзывы — единственная публичная форма записи;
она явно не является официальным обращением и не принимает заявления/заказы.
"""

from __future__ import annotations

import math
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import ColumnElement, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.service import media_url, tr_info
from app.cms import schemas as s
from app.cms.public_docs import PUBLIC_DOCS
from app.core.config import get_settings
from app.core.db import get_session
from app.core.i18n import lang_param, pick
from app.core.ratelimit import rate_limit
from app.models import Faq, FaqGroup, Feedback, News, NewsTranslation, Page
from app.models.cms import NEWS_CATEGORIES

router = APIRouter(prefix="/api", tags=["cms"])
Session = Annotated[AsyncSession, Depends(get_session)]
Lang = Annotated[str, Depends(lang_param)]
PUBLISHED = "published"
FEEDBACK_NOTICE = (
    "Спасибо! Отзыв сохранён. Это не официальное обращение: ответ по существу вопросов и регистрация "
    "обращений осуществляются через e-Otinish (eotinish.kz)."
)


def _attachments(raw: list[dict[str, Any]] | None, lang: str) -> list[s.Attachment]:
    out = []
    for a in raw or []:
        title = a.get("title") or {}
        out.append(
            s.Attachment(
                title=title.get(lang) or title.get("ru") or a.get("url", ""),
                url=a["url"],
                kind=a.get("kind", "link"),
                external=bool(a.get("external", False)),
                lang=a.get("lang"),
                verified=bool(a.get("verified", True)),
            )
        )
    return out


def _title(p: Page, lang: str) -> str | None:
    exact = next((t for t in p.translations if t.lang == lang and t.translation_status != "missing"), None)
    if exact:
        return exact.title
    picked = pick(p.translations, lang, p.original_lang)
    return picked.tr.title if picked else None


def page_out(p: Page, lang: str) -> s.PageOut:
    # Заголовок — на запрошенном языке, если переведён; тело — переведённое или оригинал с флагом фолбэка
    with_body = [t for t in p.translations if t.body]
    picked = pick(with_body or list(p.translations), lang, p.original_lang)
    assert picked is not None
    return s.PageOut(
        slug=p.slug,
        section=p.section,
        title=_title(p, lang) or picked.tr.title,
        body=picked.tr.body,
        meta_description=picked.tr.meta_description,
        actualized_at=p.actualized_at,
        attachments=_attachments(p.attachments, lang),
        data=p.data,
        is_demo=p.is_demo,
        translation=tr_info(picked),
    )


@router.get("/pages", response_model=list[s.PageLink])
async def list_pages(
    session: Session, lang: Lang, section: str | None = Query(None, max_length=32)
) -> list[s.PageLink]:
    stmt = select(Page).where(Page.workflow_status == PUBLISHED).order_by(Page.section, Page.sort_order)
    if section:
        stmt = stmt.where(Page.section == section)
    out = []
    for p in (await session.execute(stmt)).scalars():
        title = _title(p, lang)
        if title:
            out.append(s.PageLink(slug=p.slug, section=p.section, title=title))
    return out


@router.get("/pages/{slug}", response_model=s.PageOut)
async def get_page(slug: str, session: Session, lang: Lang) -> s.PageOut:
    p = (
        await session.execute(select(Page).where(Page.slug == slug, Page.workflow_status == PUBLISHED))
    ).scalar_one_or_none()
    if p is None:
        raise HTTPException(404, "Страница не найдена")
    return page_out(p, lang)


def _news_item(n: News, lang: str) -> s.NewsItem | None:
    picked = pick(n.translations, lang, n.original_lang)
    if picked is None:
        return None
    return s.NewsItem(
        id=n.id,
        slug=n.slug,
        category=n.category,
        published_at=n.published_at,
        title=picked.tr.title,
        lead=picked.tr.lead,
        cover_url=media_url(n.cover_file_id) if n.cover_file_id else None,
        is_demo=n.is_demo,
        translation=tr_info(picked),
    )


@router.get("/news", response_model=s.NewsList)
async def list_news(
    session: Session,
    lang: Lang,
    category: str | None = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    page: Annotated[int, Query(ge=1, le=500)] = 1,
    page_size: Annotated[int, Query(ge=1, le=30)] = 9,
) -> s.NewsList:
    conds: list[ColumnElement[bool]] = [News.workflow_status == PUBLISHED]
    if category and category in NEWS_CATEGORIES:
        conds.append(News.category == category)
    if q and q.strip():
        pattern = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conds.append(
            exists(
                select(NewsTranslation.entity_id).where(
                    NewsTranslation.entity_id == News.id,
                    or_(
                        NewsTranslation.title.ilike(pattern, escape="\\"),
                        NewsTranslation.lead.ilike(pattern, escape="\\"),
                    ),
                )
            )
        )
    total = (await session.execute(select(func.count()).select_from(News).where(*conds))).scalar_one()
    rows = (
        (
            await session.execute(
                select(News)
                .where(*conds)
                .order_by(News.published_at.desc().nulls_last())
                .limit(page_size)
                .offset((page - 1) * page_size)
            )
        )
        .scalars()
        .all()
    )
    items = [i for i in (_news_item(n, lang) for n in rows) if i]
    return s.NewsList(items=items, total=total, page=page, pages=math.ceil(total / page_size) if total else 0)


@router.get("/news/{slug}", response_model=s.NewsOut)
async def get_news(slug: str, session: Session, lang: Lang) -> s.NewsOut:
    n = (
        await session.execute(select(News).where(News.slug == slug, News.workflow_status == PUBLISHED))
    ).scalar_one_or_none()
    if n is None:
        raise HTTPException(404, "Новость не найдена")
    item = _news_item(n, lang)
    picked = pick(n.translations, lang, n.original_lang)
    assert item and picked
    related_rows = (
        (
            await session.execute(
                select(News)
                .where(News.workflow_status == PUBLISHED, News.category == n.category, News.id != n.id)
                .order_by(News.published_at.desc().nulls_last())
                .limit(3)
            )
        )
        .scalars()
        .all()
    )
    related = [r for r in (_news_item(x, lang) for x in related_rows) if r]
    return s.NewsOut(**item.model_dump(), body=picked.tr.body, video_url=n.video_url, related=related)


@router.get("/faq", response_model=list[s.FaqGroupOut])
async def faq(session: Session, lang: Lang) -> list[s.FaqGroupOut]:
    groups = (await session.execute(select(FaqGroup).order_by(FaqGroup.sort_order))).scalars().all()
    items = (
        (await session.execute(select(Faq).where(Faq.workflow_status == PUBLISHED).order_by(Faq.sort_order)))
        .scalars()
        .all()
    )
    out = []
    for g in groups:
        gp = pick(g.translations, lang)
        group_items = []
        for f in items:
            if f.group_id != g.id:
                continue
            fp = pick(f.translations, lang, f.original_lang)
            if fp:
                group_items.append(
                    s.FaqItem(id=f.id, question=fp.tr.question, answer=fp.tr.answer, translation=tr_info(fp))
                )
        if group_items:
            out.append(s.FaqGroupOut(slug=g.slug, title=gp.tr.title if gp else g.slug, items=group_items))
    return out


@router.post(
    "/feedback",
    response_model=s.FeedbackAck,
    status_code=201,
    dependencies=[Depends(rate_limit("5/minute", "feedback"))],
)
async def feedback(body: s.FeedbackIn, session: Session) -> s.FeedbackAck:
    # IP и user-agent не сохраняются; email — только при явном согласии (проверено в схеме)
    session.add(Feedback(message=body.message, page=body.page, email=body.email, consent=body.consent))
    await session.commit()
    return s.FeedbackAck(ok=True, notice=FEEDBACK_NOTICE)


@router.get("/public-docs/{key}", response_class=FileResponse)
async def public_doc(key: str) -> FileResponse:
    doc = PUBLIC_DOCS.get(key)
    if doc is None:
        raise HTTPException(404, "Документ не найден")
    base = get_settings().docs_source_dir.resolve()
    path = (base / doc.path).resolve()
    if base not in path.parents or not path.is_file():
        raise HTTPException(404, "Документ не найден")
    return FileResponse(
        path,
        media_type="application/pdf",
        filename=f"{key}.pdf",
        content_disposition_type="inline",
        headers={"Cache-Control": "public, max-age=86400", "X-Content-Type-Options": "nosniff"},
    )
