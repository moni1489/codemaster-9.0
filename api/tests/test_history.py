"""Сценарий 5: выставка (экспонаты с подписью и источником) и цифровая история с маркировкой."""

from httpx import AsyncClient


async def test_exhibition_has_exhibits_with_sources(client: AsyncClient) -> None:
    lst = (await client.get("/api/exhibitions")).json()
    assert len(lst) >= 1
    ex = (await client.get(f"/api/exhibitions/{lst[0]['slug']}")).json()
    assert 8 <= len(ex["exhibits"]) <= 12
    for x in ex["exhibits"]:
        assert x["caption"] and x["source_text"] and x["image_url"] and x["document"]
        assert (await client.get(x["image_url"])).status_code == 200
        assert (await client.get(f"/api/catalog/documents/{x['document']['id']}")).status_code == 200


async def test_history_marks_unverified_and_editorial(client: AsyncClient) -> None:
    cols = (await client.get("/api/history/collections")).json()
    assert 2 <= len(cols) <= 3 and any(c["editorial_note"] for c in cols)
    persons = (await client.get("/api/history/persons")).json()
    assert 3 <= len(persons) <= 5 and all(p["is_fictional"] for p in persons)
    tl = (await client.get("/api/history/timeline")).json()
    assert any(not e["date_verified"] for e in tl) and any(e["is_editorial"] for e in tl)
    war = (await client.get("/api/history/timeline", params={"topic": "war"})).json()
    assert war and all(e["topic"] == "war" for e in war)
    assert all(
        1941 <= e["year"] <= 1945
        for e in (await client.get("/api/history/timeline", params={"year_from": 1941, "year_to": 1945})).json()
    )


async def test_sitemap_only_public(client: AsyncClient, seeded: dict) -> None:  # type: ignore[type-arg]
    xml = (await client.get("/sitemap.xml")).text
    assert str(seeded["keys"]["photo-embankment-1965"]) in xml
    assert str(seeded["keys"]["hidden-cards-1950"]) not in xml and "/admin" not in xml
    assert 'hreflang="kk"' in xml
