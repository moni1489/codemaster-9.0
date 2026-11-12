"""Сценарий 2: ИИ-помощник — три обязательных кейса, валидатор, фолбэк при сбое LLM, приватность."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import pipeline
from app.ai.intent import Intent, rule_extract, validate_answer
from app.ai.providers import Record, RuleBasedProvider
from app.core.ratelimit import limiter


@pytest.fixture(autouse=True)
def _reset_limits() -> None:
    limiter.reset()


async def _ask(client: AsyncClient, q: str, lang: str = "ru") -> dict[str, Any]:
    r = await client.post("/api/assistant/ask", json={"query": q, "lang": lang})
    assert r.status_code == 200, r.text
    return r.json()


async def test_case_a_photos_1960s(client: AsyncClient) -> None:
    r = await _ask(client, "Хочу найти фотографии Усть-Каменогорска в 1960-х годах")
    assert r["status"] == "found"
    assert r["intent"]["period_from"] == 1960 and r["intent"]["period_to"] == 1969
    assert r["intent"]["doc_type"] == "photo"
    assert r["sources"] and all(s["url"].startswith("/ru/catalog/documents/") for s in r["sources"])
    for s in r["sources"]:
        card = (await client.get(f"/api/catalog/documents/{s['id']}")).json()
        assert card["cipher"] == s["cipher"] and card["category"] == "photo"
        assert 1960 <= card["year_from"] <= 1969
    assert 2 <= len(r["suggestions"]) <= 3
    assert r["disclaimer"].startswith("Сформировано автоматически")
    assert r["provider"] == "rule" and r["is_llm"] is False


async def test_case_b_nothing_found(client: AsyncClient) -> None:
    r = await _ask(client, "документы о полёте на Марс в 1812 году")
    assert r["status"] == "not_found" and r["sources"] == []
    assert "ничего не найдено" in r["text"] and "читальн" in r["text"]
    assert r["suggestions"]


async def test_case_c_restricted(client: AsyncClient) -> None:
    r = await _ask(client, "личные дела работников комбината")
    assert r["status"] == "restricted"
    assert "ограничен" in r["text"] and "читальн" in r["text"]
    assert all(s["file_access"] != "open" for s in r["sources"])
    # содержимого закрытых документов в ответе нет: только описания, без страниц
    for s in r["sources"]:
        assert (await client.get(f"/api/catalog/documents/{s['id']}")).json()["pages"] == []


async def test_hidden_records_never_reach_assistant(client: AsyncClient) -> None:
    r = await _ask(client, "личные карточки работников аппарата горисполкома секретныйтест")
    assert "Личные карточки" not in r["text"] and "СЛУЖЕБНОЕ" not in r["text"]
    assert all("Личные карточки" not in s["title"] for s in r["sources"])


@pytest.mark.parametrize(("q", "lang"), [("Өскемен фотосуреттері 1960 жылдар", "kk"), ("Oskemen photos 1960s", "en")])
async def test_multilingual(client: AsyncClient, q: str, lang: str) -> None:
    r = await _ask(client, q, lang)
    assert r["status"] == "found" and r["sources"]
    assert all(s["url"].startswith(f"/{lang}/") for s in r["sources"])


def test_validator_removes_hallucinated_cipher_id_url() -> None:
    real = "ГА ВКО Ф. Р-101 Оп. 1 Д. 27 л. 2"
    real_id = "11111111-2222-3333-4444-555555555555"
    text = (
        f"Есть фото {real}. Также см. ГА ВКО Ф. Р-999 Оп. 7 Д. 404 л. 1 и запись "
        "99999999-8888-7777-6666-555555555555, подробнее https://fake-archive.kz/doc/1 "
        f"и /ru/catalog/documents/{real_id}"
    )
    out, removed = validate_answer(text, {real}, {real_id}, {f"/ru/catalog/documents/{real_id}"})
    assert real in out and f"/ru/catalog/documents/{real_id}" in out
    assert "Р-999" not in out and "99999999-8888" not in out and "fake-archive" not in out
    assert removed == 3


def test_rule_parser() -> None:
    it = rule_extract("Хочу найти фотографии Усть-Каменогорска в 1960-х годах")
    assert (it.period_from, it.period_to, it.doc_type) == (1960, 1969, "photo")
    assert it.place == "Усть-Каменогорск"
    assert rule_extract("газеты времён ВОВ").period_from == 1941
    assert rule_extract("медицинские карты пациентов").restricted_topic


class SpyProvider:
    """Имитация внешнего LLM: запоминает, что ему передали, и «галлюцинирует» шифр."""

    name = "spy"
    is_llm = True

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.seen: list[Any] = []

    async def extract(self, query: str, lang: str) -> Intent:
        if self.fail:
            raise TimeoutError("LLM down")
        self.seen.append(("extract", query))
        return rule_extract(query)

    async def compose(self, query: str, lang: str, records: list[Record], restricted: bool) -> str:
        if self.fail:
            raise TimeoutError("LLM down")
        self.seen.append(("compose", records))
        first = records[0].cipher if records else ""
        return f"Нашёл {first}. А ещё ГА ВКО Ф. Р-555 Оп. 3 Д. 12 л. 9 — выдуманный."


async def test_llm_output_validated_and_only_public_data_sent(session: AsyncSession) -> None:
    spy = SpyProvider()
    ans = await pipeline.ask(session, "фотографии Усть-Каменогорска 1960-х", "ru", spy)
    assert "Р-555" not in ans.text and ans.removed_items == 1
    assert ans.sources[0]["cipher"] in ans.text
    records = next(x for kind, x in spy.seen if kind == "compose")
    for r in records:
        assert set(vars(r)) == {"id", "cipher", "title", "period", "summary", "file_access", "url"}
        assert "СЛУЖЕБНОЕ" not in r.summary


async def test_llm_failure_falls_back(session: AsyncSession) -> None:
    ans = await pipeline.ask(session, "фотографии Усть-Каменогорска 1960-х", "ru", SpyProvider(fail=True))
    assert ans.degraded and ans.provider == "rule" and ans.status == "found" and ans.sources


async def test_rule_provider_is_labeled(client: AsyncClient) -> None:
    mode = (await client.get("/api/assistant/mode")).json()
    assert mode["provider"] == "rule" and mode["is_llm"] is False
    assert RuleBasedProvider.is_llm is False


async def test_transcribe_disabled_without_key(client: AsyncClient) -> None:
    assert (await client.get("/api/assistant/mode")).json()["stt"] is False
    r = await client.post("/api/assistant/transcribe", files={"audio": ("a.webm", b"x" * 2000, "audio/webm")})
    assert r.status_code == 503


async def test_transcribe_rejects_non_audio(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai import router as ai_router

    monkeypatch.setattr(ai_router, "stt_enabled", lambda: True)
    r = await client.post("/api/assistant/transcribe", files={"audio": ("x.html", b"<script>" * 300, "text/html")})
    assert r.status_code == 415


def test_speech_is_short_and_clean() -> None:
    text = (
        "Нашлось записей: 6. Лучше всего подходит «Набережная Иртыша» (1965), ГА ВКО Ф. Р-101 Оп. 1 Д. 27 л. 2. "
        "Остальные — в карточках ниже. Ещё одна фраза.\n• пункт списка /ru/catalog/documents/x"
    )
    s = pipeline.to_speech(text)
    assert s == "Нашлось записей: 6. Лучше всего подходит «Набережная Иртыша» (1965)."
    assert len(pipeline.to_speech("слово " * 200)) <= 281


async def test_answer_has_short_speech(client: AsyncClient) -> None:
    r = await _ask(client, "Хочу найти фотографии Усть-Каменогорска в 1960-х годах")
    assert r["speech"] and len(r["speech"]) < len(r["text"]) + 1
    assert all(s["cipher"] not in r["speech"] for s in r["sources"])


async def test_speak_returns_audio(client: AsyncClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from app.ai import router as ai_router

    async def fake(text: str, lang: str) -> bytes:
        return b"ID3fake"

    monkeypatch.setattr(ai_router, "synthesize", fake)
    r = await client.post("/api/assistant/speak", json={"text": "Привет", "lang": "ru"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg" and r.content == b"ID3fake"
    assert (await client.post("/api/assistant/speak", json={"text": "x" * 401})).status_code == 422
