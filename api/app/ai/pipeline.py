"""ИИ-помощник: запрос → намерение (LLM/RuleBased) → поиск только по публичному индексу → ответ по найденным
записям → пост-валидатор (удаляет шифры/ID/ссылки вне выборки). Сбой LLM → детерминированный фолбэк."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.intent import CIPHER_RE, URL_RE, UUID_RE, Intent, rule_extract, validate_answer
from app.ai.providers import LLMProvider, Record, RuleBasedProvider, template_answer
from app.ai.site import SiteItem, answer_lang, contact_answer, info_template, is_info_query, search_site
from app.core.i18n import pick
from app.core.logging import log
from app.models import Document
from app.search.base import SearchParams
from app.search.postgres import get_search_backend

DISCLAIMER = {
    "ru": "Сформировано автоматически, не является архивной справкой.",
    "kk": "Автоматты түрде жасалған, архивтік анықтама болып табылмайды.",
    "en": "Generated automatically; this is not an archival certificate.",
}
NOT_FOUND = {
    "ru": "В открытом каталоге ничего не найдено. Попробуйте другие слова или более широкий период. Не всё ещё "
    "оцифровано — спросите в читальном зале архива.",
    "kk": "Ашық каталогта ештеңе табылмады. Басқа сөздерді немесе кеңірек кезеңді қолданып көріңіз, не архивтің оқу "
    "залына жүгініңіз.",
    "en": "Nothing was found in the open catalogue. Try other words or a wider period — not everything is online "
    "yet, so the reading room can help.",
}
SENTENCE_RE = re.compile(r"(?<=[.!?…])\s+")


def to_speech(text: str, max_sentences: int = 2, max_chars: int = 280) -> str:
    """Что читать вслух: без шифров, ссылок, ID и списков — только первые одна-две фразы."""
    text = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(("•", "-", "*")))
    for rx in (URL_RE, CIPHER_RE, UUID_RE):
        text = rx.sub("", text)
    text = re.sub(r"\(\s*\)|\s+([,.;:])", r"\1", re.sub(r"\s+", " ", text))
    text = re.sub(r"[,;:—–-]+\s*(?=[.!?…])", "", text).strip()  # «(1965), .» после вырезанного шифра
    out = " ".join(SENTENCE_RE.split(text)[:max_sentences])
    return out if len(out) <= max_chars else out[:max_chars].rsplit(" ", 1)[0] + "…"


CAT_WORD = {
    "ru": {"photo": "фотографии", "written": "газеты", "map": "карты"},
    "kk": {"photo": "фотосуреттер", "written": "газеттер", "map": "карталар"},
    "en": {"photo": "photos", "written": "newspapers", "map": "maps"},
}


@dataclass
class Answer:
    status: str  # found | not_found | restricted | info (ответ о самом сайте/архиве)
    text: str
    speech: str  # короткая версия для озвучки
    sources: list[dict[str, Any]]
    suggestions: list[str]
    intent: dict[str, Any]
    provider: str
    is_llm: bool
    degraded: bool = False
    removed_items: int = 0
    disclaimer: str = ""
    notes: list[str] = field(default_factory=list)
    lang: str = "ru"  # язык ответа: на казахский вопрос — по-казахски, даже на русской версии сайта


async def _search(session: AsyncSession, intent: Intent, lang: str) -> list[Document]:
    backend = get_search_backend()
    base_q = " ".join(filter(None, [intent.place, *intent.keywords])) or None
    attempts = [
        SearchParams(
            q=base_q,
            period_from=intent.period_from,
            period_to=intent.period_to,
            category=(intent.doc_type,) if intent.doc_type else (),
            page_size=8,
            lang=lang,
        ),
        SearchParams(
            q=intent.place,
            period_from=intent.period_from,
            period_to=intent.period_to,
            category=(intent.doc_type,) if intent.doc_type else (),
            page_size=8,
            lang=lang,
        ),
        SearchParams(q=base_q, period_from=intent.period_from, period_to=intent.period_to, page_size=8, lang=lang),
    ]
    for p in attempts:
        if not (p.q or p.period_from or p.category):
            continue
        res = await backend.search(session, p)
        if res.total and not res.fuzzy:
            ids = [h.document_id for h in res.hits]
            docs = {d.id: d for d in (await session.execute(select(Document).where(Document.id.in_(ids)))).scalars()}
            return [docs[i] for i in ids if i in docs]
    return []


def _record(d: Document, lang: str) -> Record:
    p = pick(d.translations, lang, d.original_lang)
    assert p is not None
    period = p.tr.period_label or (str(d.year_from) if d.year_from else "")
    return Record(
        id=str(d.id),
        cipher=d.cipher,
        title=p.tr.title,
        period=period,
        summary=p.tr.summary or "",
        file_access=d.file_access,
        url=f"/{lang}/catalog/documents/{d.id}",
    )


def _suggestions(intent: Intent, lang: str, status: str) -> list[str]:
    place = intent.place or {"ru": "Усть-Каменогорск", "kk": "Өскемен", "en": "Ust-Kamenogorsk"}[lang]
    cw = CAT_WORD[lang]
    if status == "restricted":
        return {
            "ru": ["Правила читального зала", "Как получить архивную справку", f"Открытые документы: {place}"],
            "kk": ["Оқу залының қағидалары", "Архивтік анықтаманы қалай алуға болады", f"Ашық құжаттар: {place}"],
            "en": ["Reading room rules", "How to get an archival certificate", f"Open documents: {place}"],
        }[lang]
    out: list[str] = []
    if intent.period_from:
        nxt = (
            intent.period_from + 10
            if intent.period_to and intent.period_to - intent.period_from >= 9
            else intent.period_from + 1
        )
        out.append(f"{cw['photo']} {place} {nxt}" + ("-х" if lang == "ru" and nxt % 10 == 0 else ""))
    out.append(f"{cw['written']} {place}")
    out.append(
        {
            "ru": "Великая Отечественная война в документах",
            "kk": "Ұлы Отан соғысы құжаттарда",
            "en": "Great Patriotic War in documents",
        }[lang]
    )
    return out[:3]


INFO_SUGGESTIONS = {
    "ru": ["Телефон архива", "Режим работы читального зала", "Как получить архивную справку"],
    "kk": ["Архивтің телефоны", "Оқу залының жұмыс уақыты", "Архивтік анықтаманы қалай алуға болады"],
    "en": ["Archive phone number", "Reading room hours", "How to get an archival certificate"],
}


async def _info(
    query: str,
    lang: str,
    provider: LLMProvider,
    items: list[SiteItem],
    text: str | None = None,
    speech: str | None = None,
) -> Answer:
    """Ответ о самом сайте: контакты (готовый текст) или пересказ найденных страниц/FAQ."""
    degraded, notes, name = False, [], "site"
    if text is None:
        name = provider.name
        try:
            text = await provider.answer_info(query, lang, items)
        except Exception as exc:
            log.warning("llm_info_failed", provider=provider.name, error=type(exc).__name__)
            text, degraded, name = info_template(query, lang, items), True, "rule"
            notes.append("llm_unavailable")
    text, removed = validate_answer(text, set(), set(), {it.url for it in items})
    seen: set[str] = set()
    sources = []
    for it in items:
        if it.url not in seen:
            seen.add(it.url)
            sources.append(
                {"id": it.url, "cipher": "", "title": it.title, "period": "", "file_access": "open", "url": it.url}
            )
    return Answer(
        status="info",
        text=text.strip(),
        speech=speech or to_speech(text, max_sentences=3),
        sources=sources,
        suggestions=INFO_SUGGESTIONS[lang],
        intent={},
        provider=name,
        is_llm=name not in ("site", "rule") and provider.is_llm,
        degraded=degraded,
        removed_items=removed,
        disclaimer=DISCLAIMER[lang],
        notes=notes,
        lang=lang,
    )


async def ask(session: AsyncSession, query: str, lang: str, provider: LLMProvider) -> Answer:
    lang = answer_lang(query, lang)
    # 1) телефон/адрес/почта/режим — точные данные из карточки филиала
    contact = await contact_answer(session, query, lang)
    if contact:
        return await _info(query, lang, provider, [contact[2]], text=contact[0], speech=contact[1])
    # 2) вопрос о работе архива (справки, услуги, читальный зал…), а не о документах — сначала страницы сайта
    base = rule_extract(query)
    if is_info_query(query) and not (base.period_from or base.doc_type or base.restricted_topic):
        items = await search_site(session, query, lang)
        if items:
            return await _info(query, lang, provider, items)

    degraded = False
    notes: list[str] = []
    try:
        intent = await provider.extract(query, lang)
    except Exception as exc:  # недоступен/ошибся LLM → детерминированный разбор
        log.warning("llm_extract_failed", provider=provider.name, error=type(exc).__name__)
        intent, degraded = rule_extract(query), True
        notes.append("llm_unavailable")

    docs = await _search(session, intent, lang)
    restricted = intent.restricted_topic
    if restricted:
        # показываем только опубликованные описания с закрытыми копиями — без содержимого
        docs = [d for d in docs if d.file_access != "open"]
    records = [_record(d, lang) for d in docs]
    status = "restricted" if restricted else ("found" if records else "not_found")

    if status == "not_found":
        items = await search_site(session, query, lang, strict=True)  # 3) в каталоге пусто — может, это на сайте
        if items:
            return await _info(query, lang, provider, items)
        text = NOT_FOUND[lang]
    else:
        composer: LLMProvider = provider if not degraded else RuleBasedProvider()
        try:
            text = await composer.compose(query, lang, records, restricted)
        except Exception as exc:
            log.warning("llm_compose_failed", provider=provider.name, error=type(exc).__name__)
            text, degraded = template_answer(lang, records, restricted), True
            notes.append("llm_unavailable")

    text, removed = validate_answer(
        text,
        allowed_ciphers={r.cipher for r in records},
        allowed_ids={r.id for r in records},
        allowed_urls={r.url for r in records},
    )
    sources = [
        {
            "id": r.id,
            "cipher": r.cipher,
            "title": r.title,
            "period": r.period,
            "file_access": r.file_access,
            "url": r.url,
        }
        for r in records[:6]
    ]
    return Answer(
        status=status,
        text=text.strip(),
        speech=to_speech(text),
        sources=sources,
        suggestions=_suggestions(intent, lang, status),
        intent=intent.as_dict(),
        provider="rule" if degraded else provider.name,
        is_llm=provider.is_llm and not degraded,
        degraded=degraded,
        removed_items=removed,
        disclaimer=DISCLAIMER[lang],
        notes=notes,
        lang=lang,
    )
