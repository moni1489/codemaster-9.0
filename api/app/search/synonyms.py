"""Расширение запроса синонимами и вариантами написания."""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Synonym

_WORD = re.compile(r"[\w\-]+", re.UNICODE)

# Базовый словарь (дублируется в БД сидом, чтобы редакторы могли расширять его из админки)
DEFAULT_SYNONYMS: dict[str, list[str]] = {
    "ust-kamenogorsk": [
        "Усть-Каменогорск",
        "Өскемен",
        "Оскемен",
        "Oskemen",
        "Ust-Kamenogorsk",
        "Усть-Каменогорска",
    ],
    "ridder": ["Риддер", "Лениногорск", "Ridder", "Leninogorsk"],
    "altai": ["Алтай", "Зыряновск", "Altai", "Zyryanovsk"],
    "semey": ["Семей", "Семипалатинск", "Semey", "Semipalatinsk"],
    "vov": ["ВОВ", "Великая Отечественная война", "Ұлы Отан соғысы", "Great Patriotic War", "WWII"],
    "vko": ["ВКО", "Восточно-Казахстанская область", "Шығыс Қазақстан облысы", "East Kazakhstan", "ШҚО"],
    "photo": ["фото", "фотография", "фотографии", "фотосурет", "photo", "photograph"],
    "newspaper": ["газета", "газеты", "газет", "newspaper"],
    "map": ["карта", "карты", "план", "чертеж", "чертёж", "map"],
    "kazcink": ["Казцинк", "свинцово-цинковый комбинат", "УК СЦК", "Kazzinc"],
    "irtysh": ["Иртыш", "Ертіс", "Irtysh"],
    "ulba": ["Ульба", "Үлбі", "Ulba"],
}


def normalize(text: str) -> str:
    return " ".join(text.lower().replace("ё", "е").split())


@dataclass
class Expansion:
    groups: list[list[str]]  # И между группами, ИЛИ внутри группы
    applied: list[str]  # ключи групп синонимов, которые сработали


async def load_synonyms(session: AsyncSession) -> dict[str, list[str]]:
    rows = (await session.execute(select(Synonym.group_key, Synonym.term))).all()
    groups: dict[str, list[str]] = defaultdict(list)
    for key, term in rows:
        groups[key].append(term)
    return dict(groups) or DEFAULT_SYNONYMS


def expand(query: str, synonyms: dict[str, list[str]]) -> Expansion:
    rest = f" {normalize(query)} "
    groups: list[list[str]] = []
    applied: list[str] = []
    # сначала длинные фразы: «великая отечественная война» раньше «война»
    terms = sorted(
        ((normalize(t), key) for key, ts in synonyms.items() for t in ts),
        key=lambda x: len(x[0]),
        reverse=True,
    )
    for term, key in terms:
        pattern = re.compile(rf"(?<![\w-]){re.escape(term)}(?![\w-])", re.UNICODE)
        if pattern.search(rest):
            rest = pattern.sub(" ", rest)
            if key not in applied:
                applied.append(key)
                groups.append(synonyms[key])
    groups.extend([w] for w in _WORD.findall(rest) if len(w) > 1)
    return Expansion(groups=groups, applied=applied)
