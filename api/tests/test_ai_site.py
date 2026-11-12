"""ИИ-помощник отвечает о самом сайте: контакты, услуги, цены — и по-казахски."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient

from app.ai import site
from app.core.ratelimit import limiter


@pytest.fixture(autouse=True)
def _reset_limits() -> None:
    limiter.reset()


async def _ask(client: AsyncClient, q: str, lang: str = "ru") -> dict[str, Any]:
    r = await client.post("/api/assistant/ask", json={"query": q, "lang": lang})
    assert r.status_code == 200, r.text
    return r.json()


def test_routing_helpers() -> None:
    assert site.answer_lang("архивтің телефон нөмірі қандай", "ru") == "kk"
    assert site.answer_lang("телефон архива", "en") == "en"
    assert site.is_info_query("какой номер телефона для связи с архивом")
    assert site.is_info_query("как получить архивную справку")
    assert not site.is_info_query("фотографии Усть-Каменогорска 1960-х")
    assert not site.ASK["phone"].search("номер фонда 101")
    assert site._plain("<h2>Правила</h2><p>Нужен&nbsp;паспорт.</p>") == "Правила. Нужен паспорт"


async def test_phone_from_branch_card(client: AsyncClient) -> None:
    r = await _ask(client, "какой номер телефона для связи с архивом")
    assert r["status"] == "info" and "8 (7232) 25-13-22" in r["text"]
    assert "Бухгалтерия" not in r["speech"] and "25-13-22" in r["speech"]
    assert r["sources"][0]["url"] == "/ru/branches"


async def test_kazakh_question_on_russian_site(client: AsyncClient) -> None:
    r = await _ask(client, "архивтің телефон нөмірі қандай", "ru")
    assert r["lang"] == "kk" and "Бас ғимарат" in r["text"] and r["sources"][0]["url"] == "/kk/branches"


async def test_branch_is_recognised(client: AsyncClient) -> None:
    assert "Риддер" in (await _ask(client, "телефон Риддерского филиала"))["text"]


async def test_price_from_price_list(client: AsyncClient) -> None:
    r = await _ask(client, "сколько стоит дубликат архивной справки")
    assert r["status"] == "info" and "833" in r["text"] and r["sources"][0]["url"] == "/ru/services/paid"


async def test_catalog_questions_still_go_to_catalog(client: AsyncClient) -> None:
    assert (await _ask(client, "фотографии Усть-Каменогорска 1960-х"))["status"] == "found"
    assert (await _ask(client, "личные дела работников комбината"))["status"] == "restricted"
