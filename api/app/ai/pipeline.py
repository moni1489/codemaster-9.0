"""ИИ-помощник: запрос → намерение (LLM/RuleBased) → поиск только по публичному индексу → ответ по найденным
записям → пост-валидатор (удаляет шифры/ID/ссылки вне выборки). Сбой LLM → детерминированный фолбэк."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.intent import Intent, rule_extract, validate_answer
from app.ai.providers import LLMProvider, Record, RuleBasedProvider, template_answer
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
    "ru": "В открытой части каталога по этому запросу ничего не найдено. Попробуйте другие слова, другое написание "
    "названия или более широкий период. Часть фондов ещё не описана в электронном каталоге — уточнить можно в "
    "читальном зале архива.",
    "kk": "Каталогтың ашық бөлігінде бұл сұрау бойынша ештеңе табылмады. Басқа сөздерді немесе кеңірек кезеңді "
    "қолданып көріңіз немесе архивтің оқу залына жүгініңіз.",
    "en": "Nothing was found in the open part of the catalogue. Try other words, another spelling or a wider period; "
    "some fonds are not yet described online — the reading room can help.",
}
CAT_WORD = {
    "ru": {"photo": "фотографии", "written": "газеты", "map": "карты"},
    "kk": {"photo": "фотосуреттер", "written": "газеттер", "map": "карталар"},
    "en": {"photo": "photos", "written": "newspapers", "map": "maps"},
}


@dataclass
class Answer:
    status: str  # found | not_found | restricted
    text: str
    sources: list[dict[str, Any]]
    suggestions: list[str]
    intent: dict[str, Any]
    provider: str
    is_llm: bool
    degraded: bool = False
    removed_items: int = 0
    disclaimer: str = ""
    notes: list[str] = field(default_factory=list)


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


async def ask(session: AsyncSession, query: str, lang: str, provider: LLMProvider) -> Answer:
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
        sources=sources,
        suggestions=_suggestions(intent, lang, status),
        intent=intent.as_dict(),
        provider="rule" if degraded else provider.name,
        is_llm=provider.is_llm and not degraded,
        degraded=degraded,
        removed_items=removed,
        disclaimer=DISCLAIMER[lang],
        notes=notes,
    )
