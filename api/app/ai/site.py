"""Справка по самому сайту: контакты, режим работы, услуги, читальный зал, FAQ.

Контакты отвечаются детерминированно из таблицы филиалов (номер телефона LLM не пересказывает — только копируем).
Остальное — поиск по опубликованным страницам и FAQ; найденные фрагменты отдаются LLM (или шаблону) как источники.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.i18n import pick
from app.models import Branch, Faq, Page
from app.search.synonyms import normalize

PUBLISHED = "published"
KK_LETTERS = re.compile(r"[әғқңөұүһі]", re.I)

# что именно спрашивают о контактах
ASK = {
    "phone": re.compile(
        r"телефон|номер\w*\s+(?:для\s+)?(?:связ|позвон|архив|филиал)|какой\s+номер|позвонить|дозвонит|нөмір|қоңырау|"
        r"phone|call\b"
    ),
    "address": re.compile(
        r"адрес|где\s+(?:находит|располож)\w*\s+(?:архив|филиал|читальн)|как\s+(?:добрат|доехат|пройти)|мекенжай|"
        r"(?:архив|филиал)\w*\s+қайда|address|where\s+is\s+the\s+(?:archive|branch)"
    ),
    "email": re.compile(r"e-?mail|(?:эл\.?|электронн\w*)\s*почт|почт[аыуе]\b|пошта|mail\b"),
    "director": re.compile(r"директор|руководител|кто\s+руковод|басшы|director|head\s+of"),
    "hours": re.compile(
        r"режим\s+работ|график\s+работ|час\w*\s+(?:работ|приём|прием)|когда\s+(?:работа|открыт)|время\s+работ|"
        r"выходн\w*\s+дн|жұмыс\s+(?:уақыт|кесте|тәртіб)|opening\s+hours|working\s+hours|when\s+.*\bopen|schedule"
    ),
}
CONTACTS = re.compile(r"контакт|связ\w*\s+с\s+архив|связаться|байланыс|хабарлас|contact|reach\s+the\s+archive")
# вопросы о сайте и работе архива, а не о документах
INFO = re.compile(
    r"справк|услуг|стоим|цен[аыу]\b|прейскурант|платн|бесплатн|читальн|записат|запис[ьи]\s+на|"
    r"как\s+(?:получить|заказать|подать|оформить)|правил|госуслуг|заявлен|директор|руковод|структур|"
    r"о\s+нас|об\s+архиве|анықтама|қызмет|бағасы|ақылы|тегін|оқу\s+зал|жазыл|қалай\s+алу|ереже|басшы|"
    r"certificate|service|price|cost|fee|reading\s+room|appointment|how\s+(?:to|do|can)\s+(?:get|order|apply|book)|"
    r"rules|director"
)
EXTRA_LABEL = {
    "kk": {"Приёмная": "Қабылдау бөлмесі", "Инспектор по кадрам": "Кадр инспекторы"},
    "en": {"Приёмная": "Reception", "Бухгалтерия": "Accounting", "Инспектор по кадрам": "HR inspector"},
}
# слова-связки — есть почти в любом вопросе и только мешают ранжированию
STOP_WORDS = {
    "какой", "какая", "каком", "какие", "какую", "можно", "сколько", "скажи", "скажите", "подскажите", "пожалуйста",
    "нужно", "хочу", "этом", "это", "сайт", "сайте", "сайта", "стоит", "стоят",
    "қалай", "болады", "бола", "қандай", "керек", "маған", "бар",
    "which", "where", "what", "could", "would", "about", "there", "please", "does", "have",
}  # fmt: skip
GENERIC_STEMS = {"архив", "докум", "archi", "docum"}  # встречаются на каждой странице
LABELS = {
    "ru": {"phone": "Телефон", "address": "Адрес", "email": "Электронная почта", "hours": "Режим работы",
           "director": "Руководитель",
           "unverified": "режим работы лучше уточнить по телефону"},
    "kk": {"phone": "Телефон", "address": "Мекенжай", "email": "Электрондық пошта", "hours": "Жұмыс уақыты",
           "director": "Басшы",
           "unverified": "жұмыс уақытын телефон арқылы нақтылаңыз"},
    "en": {"phone": "Phone", "address": "Address", "email": "E-mail", "hours": "Opening hours", "director": "Director",
           "unverified": "please confirm the hours by phone"},
}  # fmt: skip
GENERIC = {"филиа", "branc", "бөлім", "архив", "госуд", "главн", "здани", "ғимар", "build", "main"}
PRICE = re.compile(r"сколько\s+стоит|стоимост|цен[аыу]\b|прейскурант|тариф|бағасы|қанша\s+тұрады|price|cost|fee")
BLOCK_RE = re.compile(r"</(?:p|h\d|li|tr|div|blockquote)>|<br\s*/?>", re.I)
TAG_RE = re.compile(r"<[^>]+>")


@dataclass
class SiteItem:
    title: str
    text: str
    url: str
    faq: bool = False
    price: bool = False
    context: str = ""  # участвует только в поиске (раздел прейскуранта и т.п.), в ответ не попадает
    score: float = 0.0


def answer_lang(query: str, lang: str) -> str:
    """Спросили по-казахски на русской/английской версии — отвечаем по-казахски."""
    return "kk" if KK_LETTERS.search(query) else lang


def _stems(text: str) -> set[str]:
    # грубый стемминг для ru/kk: первые 5 букв слова — морфология обоих языков в основном в окончаниях
    # короткие слова режем до 4 букв: «копия»/«копий» → «копи»
    words = (w for w in re.findall(r"\w{4,}", normalize(text)) if w not in STOP_WORDS)
    return {w[:5] if len(w) > 5 else w[:4] for w in words} - GENERIC_STEMS


def _plain(body: str | None) -> str:
    # конец абзаца/заголовка/пункта — конец фразы, иначе «Основные правила Для работы…» слипаются
    text = BLOCK_RE.sub(". ", body or "")
    text = " ".join(html.unescape(TAG_RE.sub(" ", text)).split())
    return re.sub(r"([.!?:;])\s*\.(?:\s*\.)*", r"\1", text).strip(". ")


def is_info_query(query: str) -> bool:
    q = normalize(query)
    return bool(INFO.search(q) or CONTACTS.search(q) or any(rx.search(q) for rx in ASK.values()))


async def contact_answer(session: AsyncSession, query: str, lang: str) -> tuple[str, str, SiteItem] | None:
    """Телефон/адрес/почта/режим работы — точные данные из карточки филиала, без LLM."""
    q = normalize(query)
    asked = [k for k, rx in ASK.items() if rx.search(q)]
    if not asked and not CONTACTS.search(q):
        return None
    branches = (
        (await session.execute(select(Branch).where(Branch.visible.is_(True)).order_by(Branch.sort_order)))
        .scalars()
        .all()
    )
    if not branches:
        return None
    qs = _stems(q)

    def mentioned(b: Branch) -> bool:
        p = pick(b.translations, lang)
        names = " ".join(filter(None, [p.tr.locality, p.tr.short_name] if p else []))
        return bool((_stems(names) - GENERIC) & qs)

    main = next((b for b in branches if b.type == "main"), branches[0])
    named = [b for b in branches if mentioned(b)]
    branch = main if not named or main in named else named[0]
    p = pick(branch.translations, lang)
    if p is None:
        return None
    lb = LABELS[lang]
    parts: list[str] = []
    spoken: list[str] = []  # вслух — без доп. номеров и почтового индекса
    for key in asked or ["phone", "address", "email", "hours"]:  # «контакты» — всё, кроме руководителя
        if key == "phone" and branch.phone:
            labels = EXTRA_LABEL.get(lang, {})
            extra = "; ".join(f"{labels.get(k, k)}: {v}" for k, v in (branch.phones_extra or {}).items())
            parts.append(f"{lb['phone']}: {branch.phone}" + (f" ({extra})" if extra else "") + ".")
            spoken.append(f"{lb['phone']}: {branch.phone}.")
        elif key == "address" and p.tr.address:
            parts.append(f"{lb['address']}: {p.tr.address}.")
            spoken.append(f"{lb['address']}: {re.sub(r'^\d{6},\s*', '', p.tr.address)}.")
        elif key == "email" and branch.email:
            parts.append(f"{lb['email']}: {branch.email}.")
            spoken.append(parts[-1])
        elif key == "director" and branch.director:
            parts.append(f"{lb['director']}: {branch.director}.")
            spoken.append(parts[-1])
        elif key == "hours" and p.tr.hours:
            note = "" if branch.hours_verified else f" — {lb['unverified']}"
            parts.append(f"{lb['hours']}: {p.tr.hours}{note}.")
            spoken.append(parts[-1])
    if not parts:
        return None
    head = f"{p.tr.short_name}. "
    text = head + " ".join(parts)
    return text, head + " ".join(spoken), SiteItem(title=p.tr.name, text=text, url=f"/{lang}/branches")


def _page_url(slug: str, lang: str) -> str:
    section, *rest = slug.split("-")
    return f"/{lang}/{section}" + (f"/{'-'.join(rest)}" if rest else "")


async def search_site(
    session: AsyncSession, query: str, lang: str, limit: int = 3, strict: bool = False
) -> list[SiteItem]:
    """Поиск по опубликованным страницам и FAQ. ponytail: весь корпус читается на каждый запрос (десятки
    записей); если страниц станет сотни — индекс в Postgres FTS, как у каталога."""
    qs = _stems(query)
    if not qs:
        return []
    asks_price = bool(PRICE.search(normalize(query)))
    items: list[SiteItem] = []
    for page in (await session.execute(select(Page).where(Page.workflow_status == PUBLISHED))).scalars():
        p = pick(page.translations, lang, page.original_lang)
        if not p:
            continue
        url = _page_url(page.slug, lang)
        items.append(SiteItem(p.tr.title, _plain(p.tr.body), url))
        # прейскурант: каждая строка — отдельная «запись», чтобы на «сколько стоит …» найти нужную цену
        currency = (page.data or {}).get("currency", "")
        for sec in (page.data or {}).get("sections") or []:
            parent = ""  # строка без цены — заголовок для следующих («Цифровая копия …» → «формат А4: …»)
            for row in sec.get("rows") or []:
                if not row.get("price"):
                    parent = row.get("name", "").rstrip(":")
                    continue
                unit = f" ({row['unit']})" if row.get("unit") else ""
                name = f"{parent}: {row['name']}" if parent else row["name"]
                text = f"{name}{unit}: {row['price']} {currency}."
                items.append(SiteItem(p.tr.title, text, url, price=True, context=sec.get("title", "")))
    for faq in (await session.execute(select(Faq).where(Faq.workflow_status == PUBLISHED))).scalars():
        f = pick(faq.translations, lang, faq.original_lang)
        if f:
            items.append(SiteItem(f.tr.question, _plain(f.tr.answer), f"/{lang}/faq", faq=True))
    for it in items:
        title_hits = len(qs & _stems(it.title))
        body = _stems(f"{it.text} {it.context}")
        body_hits = len(qs & body)
        if strict and not qs <= body | _stems(it.title):  # запасной путь: на странице должны быть все слова вопроса
            continue
        it.score = (2 * title_hits + body_hits) / len(qs) + (2 if it.price and asks_price else 0)
    found = sorted((it for it in items if it.score >= 0.5), key=lambda it: it.score, reverse=True)
    return found[:limit]


SENT_RE = re.compile(r"(?<=[.!?])\s+")
MORE = {"ru": "Подробнее — на странице «{t}».", "kk": "Толығырақ — «{t}» бетінде.", "en": "More on the page “{t}”."}


def best_snippet(text: str, query: str, n: int = 2) -> str:
    """Самые подходящие к вопросу предложения страницы (в исходном порядке)."""
    sents = [x for x in SENT_RE.split(text) if x.strip()]
    qs = _stems(query)
    ranked = sorted(range(len(sents)), key=lambda i: -len(qs & _stems(sents[i])))[:n]
    return " ".join(sents[i] for i in sorted(ranked))


def info_template(query: str, lang: str, items: list[SiteItem]) -> str:
    top = items[0]
    if top.faq:  # ответ FAQ без самого вопроса бывает непонятен («Нет. …»)
        return f"{top.title} {best_snippet(top.text, query)}"
    return f"{best_snippet(top.text, query)} {MORE[lang].format(t=top.title)}".strip()


def site_block(query: str, items: list[SiteItem]) -> str:
    rows = [f"[{it.title}] {best_snippet(it.text, query, 4)[:700]}" for it in items]
    return "<site>\n" + "\n".join(rows) + "\n</site>"
