"""Провайдеры LLM. Внешнему сервису передаётся ТОЛЬКО текст запроса и публичные метаданные найденных записей."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from app.ai.intent import Intent, rule_extract
from app.core.config import get_settings

LANG_NAME = {"ru": "русском", "kk": "казахском", "en": "английском"}


@dataclass
class Record:
    """Публичные метаданные записи — всё, что может увидеть LLM."""

    id: str
    cipher: str
    title: str
    period: str
    summary: str
    file_access: str
    url: str


class LLMProvider(Protocol):
    name: str
    is_llm: bool

    async def extract(self, query: str, lang: str) -> Intent: ...

    async def compose(self, query: str, lang: str, records: list[Record], restricted: bool) -> str: ...


TEMPLATES = {
    "ru": {
        "found": "По запросу найдено записей в открытой части каталога: {n}. Наиболее подходящие:",
        "restricted": "Материалы по этой теме существуют или могут существовать, но доступ к ним ограничен "
        "(персональные данные / сведения ограниченного доступа). Содержимое и цифровые копии на сайте не "
        "публикуются — обратитесь в читальный зал архива или через официальные каналы госуслуги.",
        "restricted_found": "Ниже — опубликованные описания, цифровые копии которых закрыты:",
        "item": "• {title} ({period}) — шифр {cipher}{lock}",
        "lock": ", копия закрыта",
    },
    "kk": {
        "found": "Каталогтың ашық бөлігінде табылған жазбалар: {n}. Ең сәйкестері:",
        "restricted": "Бұл тақырып бойынша материалдар бар немесе болуы мүмкін, бірақ оларға қолжетімділік шектелген. "
        "Мазмұны мен цифрлық көшірмелері сайтта жарияланбайды — архивтің оқу залына жүгініңіз.",
        "restricted_found": "Төменде цифрлық көшірмелері жабық жарияланған сипаттамалар:",
        "item": "• {title} ({period}) — шифр {cipher}{lock}",
        "lock": ", көшірме жабық",
    },
    "en": {
        "found": "Records found in the open part of the catalogue: {n}. Best matches:",
        "restricted": "Materials on this topic exist or may exist, but access to them is restricted. Their content "
        "and digital copies are not published on this website — please contact the archive reading room.",
        "restricted_found": "Below are published descriptions whose digital copies are closed:",
        "item": "• {title} ({period}) — reference {cipher}{lock}",
        "lock": ", copy closed",
    },
}


def template_answer(lang: str, records: list[Record], restricted: bool) -> str:
    t = TEMPLATES.get(lang, TEMPLATES["ru"])
    lines: list[str] = []
    if restricted:
        lines.append(t["restricted"])
        if records:
            lines.append(t["restricted_found"])
    elif records:
        lines.append(t["found"].format(n=len(records)))
    for r in records[:5]:
        lines.append(
            t["item"].format(
                title=r.title,
                period=r.period or "—",
                cipher=r.cipher,
                lock=t["lock"] if r.file_access != "open" else "",
            )
        )
    return "\n".join(lines)


class RuleBasedProvider:
    """Демо-режим без LLM: детерминированный разбор и шаблонный ответ."""

    name = "rule"
    is_llm = False

    async def extract(self, query: str, lang: str) -> Intent:
        return rule_extract(query)

    async def compose(self, query: str, lang: str, records: list[Record], restricted: bool) -> str:
        return template_answer(lang, records, restricted)


EXTRACT_PROMPT = (
    "Разбери поисковый запрос к каталогу архива Восточно-Казахстанской области. Верни только JSON-объект с ключами "
    "topic (строка|null), period_from (год|null), period_to (год|null), place (населённый пункт|null), "
    "doc_type (одно из photo, map, written, personal, organization, historical или null), keywords (массив до 6 "
    "значимых слов на языке запроса), restricted_topic (true, если спрашивают о личных делах, судебных, "
    "медицинских или иных сведениях с персональными данными). «1960-е» → 1960–1969."
)


def compose_prompt(lang: str, restricted: bool) -> str:
    return (
        f"Ты — справочный помощник сайта Государственного архива ВКО. Отвечай на {LANG_NAME.get(lang, 'русском')} "
        "языке, кратко (до 120 слов). Используй ТОЛЬКО записи из блока <records>; не придумывай документы, шифры, "
        "идентификаторы и ссылки — шифры копируй дословно. Если записей нет, честно скажи, что в открытой части "
        "каталога ничего не найдено, и посоветуй переформулировать запрос или обратиться в читальный зал. "
        + (
            "Запрос касается сведений ограниченного доступа: скажи, что материалы могут существовать, но доступ "
            "ограничен, и направь в читальный зал; не пересказывай содержание. "
            if restricted
            else ""
        )
        + "Не обещай выдать справку — сайт не принимает заявления. Не используй разметку Markdown."
    )


def records_block(records: list[Record]) -> str:
    rows = [
        {
            "cipher": r.cipher,
            "title": r.title,
            "period": r.period,
            "summary": r.summary[:300],
            "copy": "open" if r.file_access == "open" else "closed",
        }
        for r in records[:8]
    ]
    return "<records>" + json.dumps(rows, ensure_ascii=False) + "</records>"


def _intent_from_json(data: dict[str, Any], query: str) -> Intent:
    base = rule_extract(query)  # страховка: детерминированные признаки + то, что вернула модель

    def as_year(v: Any) -> int | None:
        try:
            y = int(v)
        except (TypeError, ValueError):
            return None
        return y if 1500 <= y <= 2100 else None

    kws = [str(k)[:40] for k in (data.get("keywords") or []) if str(k).strip()][:6]
    return Intent(
        topic=(str(data["topic"])[:100] if data.get("topic") else base.topic),
        period_from=as_year(data.get("period_from")) or base.period_from,
        period_to=as_year(data.get("period_to")) or base.period_to,
        place=(str(data["place"])[:60] if data.get("place") else base.place),
        doc_type=data.get("doc_type")
        if data.get("doc_type") in {"photo", "map", "written", "personal", "organization", "historical"}
        else base.doc_type,
        keywords=kws or base.keywords,
        restricted_topic=bool(data.get("restricted_topic")) or base.restricted_topic,
    )


def _json_from_text(text: str) -> dict[str, Any]:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no json")
    data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("not an object")
    return data


class AnthropicProvider:
    name = "anthropic"
    is_llm = True

    def __init__(self) -> None:
        import anthropic

        s = get_settings()
        self.model = s.anthropic_model
        self.client = anthropic.AsyncAnthropic(
            api_key=s.anthropic_api_key.get_secret_value(), timeout=s.llm_timeout_seconds, max_retries=1
        )

    async def _ask(self, system: str, user: str, max_tokens: int) -> str:
        # server-side fallback при отказе классификатора; effort low — короткие справочные ответы
        resp = await self.client.beta.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
        if resp.stop_reason == "refusal":
            raise RuntimeError("refusal")
        return "".join(b.text for b in resp.content if b.type == "text")

    async def extract(self, query: str, lang: str) -> Intent:
        text = await self._ask(EXTRACT_PROMPT, query, 1024)
        return _intent_from_json(_json_from_text(text), query)

    async def compose(self, query: str, lang: str, records: list[Record], restricted: bool) -> str:
        return await self._ask(compose_prompt(lang, restricted), f"{records_block(records)}\n\nВопрос: {query}", 2048)


class OllamaProvider:
    name = "ollama"
    is_llm = True

    def __init__(self) -> None:
        s = get_settings()
        self.url = s.ollama_url.rstrip("/") + "/api/chat"
        self.model = s.ollama_model
        self.timeout = s.llm_timeout_seconds

    async def _chat(self, system: str, user: str, json_mode: bool) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        }
        if json_mode:
            payload["format"] = "json"
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.post(self.url, json=payload)
            r.raise_for_status()
            return str(r.json()["message"]["content"])

    async def extract(self, query: str, lang: str) -> Intent:
        return _intent_from_json(_json_from_text(await self._chat(EXTRACT_PROMPT, query, True)), query)

    async def compose(self, query: str, lang: str, records: list[Record], restricted: bool) -> str:
        return await self._chat(compose_prompt(lang, restricted), f"{records_block(records)}\n\nВопрос: {query}", False)


class OpenRouterProvider:
    """OpenAI-совместимый API OpenRouter (бесплатные модели). Передаются только запрос и публичные метаданные."""

    name = "openrouter"
    is_llm = True
    URL = "https://openrouter.ai/api/v1/chat/completions"
    # бесплатные модели часто упираются в общий лимит — OpenRouter сам переключится на следующую из списка
    FALLBACKS = (
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "nvidia/nemotron-3.5-super-vl:free",
        "google/gemma-4-31b-it:free",
    )

    def __init__(self) -> None:
        s = get_settings()
        self.key = s.openrouter_api_key.get_secret_value()
        self.model = s.openrouter_model
        self.timeout = s.llm_timeout_seconds

    async def _chat(self, system: str, user: str) -> str:
        payload = {
            "models": [self.model, *(m for m in self.FALLBACKS if m != self.model)][:3],
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {self.key}", "X-Title": "VKO Archive prototype"}
        async with httpx.AsyncClient(timeout=self.timeout) as c:
            r = await c.post(self.URL, json=payload, headers=headers)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
        if not content:
            raise RuntimeError("empty completion")
        return str(content)

    async def extract(self, query: str, lang: str) -> Intent:
        return _intent_from_json(_json_from_text(await self._chat(EXTRACT_PROMPT, query)), query)

    async def compose(self, query: str, lang: str, records: list[Record], restricted: bool) -> str:
        return await self._chat(compose_prompt(lang, restricted), records_block(records) + "\n\nВопрос: " + query)


def get_provider() -> LLMProvider:
    s = get_settings()
    mode = s.llm_provider
    if mode == "anthropic" or (mode == "auto" and s.anthropic_api_key.get_secret_value()):
        return AnthropicProvider()
    if mode == "openrouter" or (mode == "auto" and s.openrouter_api_key.get_secret_value()):
        return OpenRouterProvider()
    if mode == "ollama":
        return OllamaProvider()
    return RuleBasedProvider()
