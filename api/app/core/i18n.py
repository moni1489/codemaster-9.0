"""Выбор перевода с фолбэком на оригинал (D-009)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

from fastapi import Query

from app.models.base import TranslationMixin
from app.models.enums import DEFAULT_LANG, LANGS

T = TypeVar("T", bound=TranslationMixin)


@dataclass(frozen=True)
class Picked(Generic[T]):
    tr: T
    requested_lang: str
    lang: str  # язык фактически отданного текста
    status: str  # original | verified | machine | missing (если отдан фолбэк)

    @property
    def is_fallback(self) -> bool:
        return self.lang != self.requested_lang


def pick(translations: list[T], lang: str, original_lang: str = DEFAULT_LANG) -> Picked[T] | None:
    by_lang = {t.lang: t for t in translations}
    exact = by_lang.get(lang)
    if exact is not None and exact.translation_status != "missing":
        return Picked(exact, lang, lang, exact.translation_status)
    for candidate in (original_lang, DEFAULT_LANG, *LANGS):
        tr = by_lang.get(candidate)
        if tr is not None and tr.translation_status != "missing":
            return Picked(tr, lang, candidate, "missing")
    return None


def lang_param(lang: str = Query(DEFAULT_LANG, pattern="^(kk|ru|en)$")) -> str:
    return lang
