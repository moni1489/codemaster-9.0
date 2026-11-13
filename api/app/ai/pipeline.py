"""ИИ-помощник: запрос → намерение (LLM/RuleBased) → поиск только по публичному индексу → ответ по найденным
записям → пост-валидатор (удаляет шифры/ID/ссылки вне выборки). Сбой LLM → детерминированный фолбэк."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import partial
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.intent import CIPHER_RE, URL_RE, UUID_RE, Intent, rule_extract, validate_answer
from app.ai.providers import LLMProvider, Record, RuleBasedProvider, _intent_from_json, template_answer
from app.ai.site import SiteItem, _stems, answer_lang, contact_answer, info_template, is_info_query, search_site
from app.core.i18n import pick
from app.core.logging import log
from app.models import Document
from app.search.base import SearchParams
from app.search.postgres import get_search_backend
from app.search.synonyms import normalize

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
# голос читает это как «бэкслэш», «звёздочка»…: разметка и экранирование от LLM, служебные пометки валидатора
THINK_RE = re.compile(r"<think>.*?(?:</think>|$)", re.S)
NOTE_RE = re.compile(r"\[[^\]]*\]")
ANSWER_LABEL_RE = re.compile(r"^\s*(?:ответ|жауап|answer)\s*:\s*", re.I)
JUNK_RE = re.compile(r"\\[ntr\"']?|[*_#`|<>{}~^/]")


def to_speech(text: str, max_sentences: int = 2, max_chars: int = 280) -> str:
    """Что читать вслух: только сам ответ — без шифров, ссылок, ID, списков, разметки; первые одна-две фразы."""
    text = THINK_RE.sub("", text).replace("\\n", "\n")
    text = "\n".join(ln for ln in text.splitlines() if not ln.lstrip().startswith(("•", "-", "*")))
    for rx in (URL_RE, CIPHER_RE, UUID_RE, NOTE_RE):
        text = rx.sub("", text)
    text = ANSWER_LABEL_RE.sub("", JUNK_RE.sub(" ", text))
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
    action_url: str = ""  # «Позвонить?» / «Открыть в 2ГИС?» — на «да» чат открывает эту ссылку
    action: str = ""  # call | map


async def _search(session: AsyncSession, intent: Intent, lang: str) -> tuple[list[Document], set[Any]]:
    """Несколько попыток от точной к широкой; результаты объединяются. Вторым значением — id записей,
    найденных по словам темы (полнотекстовый поиск с морфологией и синонимами), а не только по месту/типу."""
    backend = get_search_backend()
    base_q = " ".join(filter(None, [intent.place, *intent.keywords])) or None
    cat = (intent.doc_type,) if intent.doc_type else ()
    mk = partial(SearchParams, period_from=intent.period_from, period_to=intent.period_to, page_size=8, lang=lang)
    # названные место и тип документа не ослабляем: «фото мостов Риддера» — не «решение о мосте через Иртыш»
    attempts = [
        (mk(q=base_q, category=cat), True),  # место + тема + тип
        (mk(q=intent.place, category=cat), False),  # то же без темы — только как «ближе всего»
    ]
    ids: list[Any] = []
    exact: set[Any] = set()
    for p, by_topic in attempts:
        if not (p.q or p.period_from or p.category):
            continue
        res = await backend.search(session, p)
        if res.total and not res.fuzzy:
            found = [h.document_id for h in res.hits]
            ids += [i for i in found if i not in ids]
            if by_topic and intent.keywords:
                exact.update(found)
        if len(ids) >= 8:
            break
    if not ids:
        return [], exact
    docs = {d.id: d for d in (await session.execute(select(Document).where(Document.id.in_(ids)))).scalars()}
    return [docs[i] for i in ids[:8] if i in docs], exact


async def _llm_intent(provider: LLMProvider, query: str, lang: str, fallback: Intent, notes: list[str]) -> Intent:
    try:
        return await provider.extract(query, lang)
    except Exception as exc:  # недоступен/ошибся LLM → детерминированный разбор
        log.warning("llm_extract_failed", provider=provider.name, error=type(exc).__name__)
        notes.append("llm_unavailable")
        return fallback


async def _find(session: AsyncSession, intent: Intent, lang: str) -> tuple[list[Record], bool]:
    """Записи для ответа и признак «точного нет, только похожее»."""
    docs, exact = await _search(session, intent, lang)
    if intent.restricted_topic:
        # показываем только опубликованные описания с закрытыми копиями — без содержимого
        docs = [d for d in docs if d.file_access != "open"]
    records = [_record(d, lang) for d in docs]
    # тема важнее места: «старые рудничные постройки в Лениногорске» выше «центральной площади Лениногорска»
    exact_ids = {str(i) for i in exact}
    scores = {r.id: _overlap(r, intent) + (1 if r.id in exact_ids else 0) for r in records}
    records.sort(key=lambda r: -scores[r.id])  # sort стабильный — внутри равных сохраняется порядок поиска
    loose = bool(intent.keywords) and bool(records) and scores[records[0].id] == 0
    if not loose and intent.keywords:
        records = [r for r in records if scores[r.id] > 0]  # есть точные — случайные «по месту» не нужны
    return records[:6], loose  # столько же, сколько карточек под ответом


def _overlap(r: Record, intent: Intent) -> int:
    """Сколько слов темы вопроса есть в названии/описании записи."""
    return len(_stems(" ".join(intent.keywords)) & _stems(f"{r.title} {r.summary}"))


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


# Уточняющий вопрос: «а 1970-х?», «а газеты?», «а адрес?», «ал Риддерде?» — продолжает предыдущий
FOLLOW_RE = re.compile(r"^(?:а|и|ещё|еще|тогда|также|теперь|ал|және|тағы|енді|and|also|now|what\s+about|how\s+about)\b")


@dataclass
class Turn:
    """Предыдущий вопрос сессии (присылает браузер): текст и разобранный запрос."""

    q: str
    intent: dict[str, Any] | None = None


def _is_follow_up(query: str, it: Intent) -> bool:
    q = normalize(query)
    return bool(FOLLOW_RE.match(q)) or (len(q.split()) <= 3 and not it.place and not it.keywords)


def _merge(it: Intent, prev: Intent) -> Intent:
    """Недостающее в уточнении берём из прошлого вопроса; новая тема заменяет старую."""
    new_topic = bool(it.keywords) or (it.doc_type is not None and it.doc_type != prev.doc_type)
    return Intent(
        topic=it.topic if new_topic else prev.topic,
        period_from=it.period_from or prev.period_from,
        period_to=it.period_to or prev.period_to,
        place=it.place or prev.place,
        doc_type=it.doc_type or prev.doc_type,
        keywords=it.keywords if new_topic else prev.keywords,
        restricted_topic=it.restricted_topic or prev.restricted_topic,
    )


def _useful(it: Intent) -> bool:
    return bool(it.place or it.period_from or it.doc_type or it.restricted_topic or len(it.keywords) >= 2)


async def ask(
    session: AsyncSession, query: str, lang: str, provider: LLMProvider, history: list[Turn] | None = None
) -> Answer:
    base = rule_extract(query)
    prev = history[-1] if history else None
    follow = prev is not None and _is_follow_up(query, base)
    # для поиска по сайту и для LLM уточнение склеиваем с прошлым вопросом: «телефон Риддерского филиала» + «а адрес?»
    site_q = f"{prev.q} {query}" if follow and prev else query
    llm_q = f"(Предыдущий вопрос: {prev.q})\n{query}" if follow and prev else query
    lang = answer_lang(site_q, lang)  # «ал 1960 жылдар?» после казахского вопроса — тоже по-казахски

    # 1) телефон/адрес/почта/режим — точные данные из карточки филиала
    contact = await contact_answer(session, query, lang, context=prev.q if follow and prev else "")
    if contact:
        answer = await _info(llm_q, lang, provider, [contact[2]], text=contact[0], speech=contact[1])
        answer.action, answer.action_url = contact[2].action, contact[2].action_url
        return answer
    # 2) вопрос о работе архива (справки, услуги, читальный зал…), а не о документах — сначала страницы сайта
    if is_info_query(site_q) and not (base.period_from or base.doc_type or base.restricted_topic):
        items = await search_site(session, site_q, lang)
        if items:
            return await _info(llm_q, lang, provider, items)

    degraded = False
    notes: list[str] = []
    intent = base
    asked_llm = False
    # LLM разбирает запрос, только если правила ничего не поняли: так ответ приходит вдвое быстрее
    if provider.is_llm and not _useful(base) and not follow:
        intent, asked_llm = await _llm_intent(provider, query, lang, base, notes), True
    if follow and prev:
        intent = _merge(intent, _intent_from_json(prev.intent or {}, prev.q))
    records, loose = await _find(session, intent, lang)
    # точного нет — возможно, правила не поняли запрос (ошибки распознавания речи): пусть LLM восстановит смысл
    if (loose or not records) and provider.is_llm and not asked_llm:
        retry = await _llm_intent(provider, query, lang, base, notes)
        if follow and prev:
            retry = _merge(retry, _intent_from_json(prev.intent or {}, prev.q))
        if retry.as_dict() != intent.as_dict():
            r2, l2 = await _find(session, retry, lang)
            if r2 and (not l2 or not records):
                intent, records, loose = retry, r2, l2
    # «ближе всего» имеет смысл, только если совпало место или период — иначе это случайная запись
    if loose and not (intent.place or intent.period_from):
        records, loose = [], False
    restricted = intent.restricted_topic
    query = llm_q

    status = "restricted" if restricted else ("found" if records else "not_found")

    if status == "not_found":
        items = await search_site(session, query, lang, strict=True)  # 3) в каталоге пусто — может, это на сайте
        if items:
            return await _info(query, lang, provider, items)
        text = NOT_FOUND[lang]
    else:
        composer: LLMProvider = provider if not degraded else RuleBasedProvider()
        try:
            text = (
                template_answer(lang, records, restricted, loose)
                if isinstance(composer, RuleBasedProvider)
                else await composer.compose(query, lang, records, restricted)
            )
        except Exception as exc:
            log.warning("llm_compose_failed", provider=provider.name, error=type(exc).__name__)
            text, degraded = template_answer(lang, records, restricted, loose), True
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
