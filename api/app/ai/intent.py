"""Детерминированный разбор запроса (RuleBased) и проверка «галлюцинаций» в ответе."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any

from app.search.synonyms import DEFAULT_SYNONYMS, normalize


@dataclass
class Intent:
    topic: str | None = None
    period_from: int | None = None
    period_to: int | None = None
    place: str | None = None
    doc_type: str | None = None  # категория каталога: photo | map | written | personal …
    keywords: list[str] = field(default_factory=list)
    restricted_topic: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# Темы, по которым документы обычно имеют ограниченный доступ (персональные данные и т.п.) — D-005
RESTRICTED = re.compile(
    r"личн\w*\s+(?:дел|карточ)|по\s+личному\s+составу|кадр\w*|анкет|судебн|следствен|уголовн|медицин|диагноз|"
    r"репресс|персональн\w*\s+дан|жеке\s+(?:іс|құрам)|personnel|personal\s+file|criminal|medical"
)
CATEGORY_WORDS = {
    "photo": ("фото", "фотограф", "снимк", "фотосурет", "photo"),
    "map": ("карт", "план", "чертеж", "чертёж", "схем", "map"),
    "written": ("газет", "newspaper", "газет"),
    "personal": ("письм", "дневник", "воспомин", "хат", "letter", "memoir"),
    "organization": ("приказ", "протокол", "отчёт", "отчет", "решени", "бұйрық", "order", "report"),
}
STOP = {
    "хочу", "найти", "найди", "покажи", "есть", "ли", "в", "во", "на", "о", "об", "про", "по", "и", "а", "годах",
    "годы", "год", "года", "лет", "гг", "архив", "архиве", "документы", "документ", "материалы", "какие",
    "мне", "нужны", "нужно", "the", "of", "in", "find", "show", "me", "i", "want", "any", "documents", "about",
    "жылдардағы", "жылдар", "туралы", "құжаттар", "керек", "что", "где", "with", "показать", "открой",
    "көрсет", "көрсетіңіз", "көрсетші", "көрсетше", "маған", "времен", "время", "годов",
    "жылдарының", "жылдары", "жылдардың",
    "предыдущие", "вопросы", "текущий", "вопрос", "документах", "документов",
}  # fmt: skip


# «военных лет», «годы войны» — это 1941–1945; сами слова тогда не ключевые (в названиях документов их нет)
VOV_PHRASES = (
    "вов", "великой отечественн", "великая отечественн", "войны 1941", "военных лет", "военные годы",
    "военного времени", "военное время", "годы войны", "время войны", "в войну",
    "ұлы отан", "соғыс жылдар", "wwii", "great patriotic", "wartime", "war years",
)  # fmt: skip
VOV_STEMS = ("вов", "военн", "войн", "великая", "великой", "отечеств", "соғыс", "ұлы", "отан", "wartime", "war")


def parse_period(q: str) -> tuple[int | None, int | None]:
    low = q.lower()
    m = re.search(r"(1[6-9]\d0|20[0-2]0)\s*-?\s*(?:е|х|ых|ые|s|'s|жылдар|жж)", low)
    if m:
        start = int(m.group(1))
        return start, start + 9
    m = re.search(r"(1[6-9]\d\d|20[0-2]\d)\s*[–—-]\s*(1[6-9]\d\d|20[0-2]\d)", low)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"\b(1[6-9]\d\d|20[0-2]\d)\b", low)
    if m:
        y = int(m.group(1))
        return y, y
    if any(w in low for w in VOV_PHRASES):
        return 1941, 1945
    return None, None


def fuzzy_place(word: str) -> list[str] | None:
    """Название места с ошибкой распознавания. Только длинные названия и общее начало слова:
    иначе «семена» становятся Семеем."""
    for key, terms in DEFAULT_SYNONYMS.items():
        if key in ("photo", "newspaper", "map", "vov", "vko"):
            continue
        for t in (normalize(x) for x in terms):
            if len(t) >= 6 and word[:2] == t[:2]:
                r = max(SequenceMatcher(None, word, t).ratio(), SequenceMatcher(None, word[: len(t)], t).ratio())
                if r >= 0.7:
                    return terms
    return None


# «көрсетші» и то, во что его превращает распознавание речи («қор сетті») — это команда, а не тема
SHOW_KK_RE = re.compile(r"(?<!\w)(?:көр|қор)\s?сет\w*")


def rule_extract(query: str) -> Intent:
    q = SHOW_KK_RE.sub(" ", normalize(query))
    it = Intent()
    it.period_from, it.period_to = parse_period(q)
    it.restricted_topic = bool(RESTRICTED.search(q))
    for cat, stems in CATEGORY_WORDS.items():
        if any(w in q for w in stems):
            it.doc_type = cat
            break
    place_stems: list[str] = []
    for key, terms in DEFAULT_SYNONYMS.items():
        if key in ("photo", "newspaper", "map", "vov", "vko"):
            continue
        if any(normalize(t)[:6] in q for t in terms):
            it.place = terms[0]
            place_stems = [normalize(t)[:6] for t in terms]  # «Лениногорске» — это тоже место, не ключевое слово
            break
    if not it.place:  # распознавание речи коверкает названия: «өскімін» → Өскемен
        for w in re.findall(r"[\w\-]{5,}", q):
            hit = fuzzy_place(w)
            if hit:
                it.place, place_stems = hit[0], [w[:6]]
                break
    words = re.findall(r"[\w\-]+", q)
    cat_stems = [w for ws in CATEGORY_WORDS.values() for w in ws]
    kws = []
    for w in words:
        if w in STOP or len(w) < 3 or re.fullmatch(r"\d+.*", w):
            continue
        # категория «written» — это все письменные документы, поэтому «газета» остаётся словом поиска
        if any(w.startswith(s) for s in cat_stems) and not w.startswith(("газет", "newspaper", "газеттер")):
            continue
        if any(ps in w for ps in place_stems):
            continue
        if it.period_from == 1941 and it.period_to == 1945 and w.startswith(VOV_STEMS):
            continue
        kws.append(w)
    it.keywords = kws[:6]
    it.topic = " ".join(kws[:3]) or None
    return it


CIPHER_RE = re.compile(r"(?:ГА\s*ВКО\s*)?Ф\.\s*[А-ЯA-ZЁ]-?\d+(?:\s*Оп\.\s*\d+)?(?:\s*Д\.\s*\d+)?(?:\s*л\.\s*[\d–\-]+)?")
UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)
URL_RE = re.compile(r"(?:https?://|/(?:ru|kk|en)/|/api/)[^\s)\]»\"']+")


def validate_answer(
    text: str, allowed_ciphers: set[str], allowed_ids: set[str], allowed_urls: set[str]
) -> tuple[str, int]:
    """Удалить из ответа ИИ шифры, идентификаторы и ссылки, которых нет в найденной выборке."""
    removed = 0
    norm_allowed = {re.sub(r"\s+", " ", c).strip() for c in allowed_ciphers}

    def cipher_ok(m: re.Match[str]) -> str:
        nonlocal removed
        found = re.sub(r"\s+", " ", m.group(0)).strip()
        if any(found in c or c in found for c in norm_allowed if len(found) >= 8):
            return m.group(0)
        removed += 1
        return "[шифр удалён: нет в результатах поиска]"

    def id_ok(m: re.Match[str]) -> str:
        nonlocal removed
        if m.group(0).lower() in allowed_ids:
            return m.group(0)
        removed += 1
        return "[удалено]"

    def url_ok(m: re.Match[str]) -> str:
        nonlocal removed
        if m.group(0).rstrip(".,;:") in allowed_urls:
            return m.group(0)
        removed += 1
        return "[ссылка удалена]"

    text = URL_RE.sub(url_ok, text)
    text = CIPHER_RE.sub(cipher_ok, text)
    text = UUID_RE.sub(id_ok, text)
    return text, removed
