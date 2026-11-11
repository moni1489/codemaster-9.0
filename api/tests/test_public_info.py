"""Публичные справочники: филиалы (координаты не выдаются за проверенные) и памятные даты."""

from __future__ import annotations

from httpx import AsyncClient


async def test_branches_main_plus_13(client: AsyncClient) -> None:
    items = (await client.get("/api/branches")).json()
    assert len(items) == 14
    assert [b["type"] for b in items].count("main") == 1
    # приблизительные координаты не представлены как проверенные (Д §3.3)
    assert all(b["coords_verified"] is False for b in items)
    assert sum(1 for b in items if b["lat"] is None) == 2


async def test_branch_translation_marked_machine(client: AsyncClient) -> None:
    b = (await client.get("/api/branches/ridder", params={"lang": "kk"})).json()
    assert b["translation"]["status"] == "machine"
    assert (await client.get("/api/branches/nope")).status_code == 404


async def test_memorial_today_exact_date(client: AsyncClient) -> None:
    r = (await client.get("/api/memorial-dates/today", params={"on": "2026-01-08"})).json()
    assert r["exact"] is True
    assert any("Пермитин" in i["title"] for i in r["items"])


async def test_memorial_today_kk_and_nearest(client: AsyncClient) -> None:
    r = (await client.get("/api/memorial-dates/today", params={"on": "2026-11-12", "lang": "kk"})).json()
    assert r["items"], "должны быть ближайшие даты месяца"
    assert all(i["title"] for i in r["items"])


async def test_memorial_by_year(client: AsyncClient) -> None:
    items = (await client.get("/api/memorial-dates", params={"year": 2025, "month": 8})).json()
    assert any("Абая" in i["title"] for i in items)
