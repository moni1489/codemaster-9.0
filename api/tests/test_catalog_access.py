"""Сценарий 1 (Д §6 «Поиск документа») и правила доступа D-004.

Поиск → фильтр → карточка → просмотр открытого скана; закрытый файл: прямой URL 403, API 403,
скрытые описания отсутствуют в поиске и индексе.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.routing import Mount

from app.main import create_app
from app.media import storage
from app.models import DigitalFile, Document, SearchIndex
from app.search.postgres import get_search_backend


async def _files(session: AsyncSession, doc_id: uuid.UUID) -> dict[str, DigitalFile]:
    rows = (await session.execute(select(DigitalFile).where(DigitalFile.document_id == doc_id))).scalars().all()
    return {f.kind: f for f in rows}


async def test_search_filter_card_view_open_scan(client: AsyncClient) -> None:
    # 1. поиск
    r = await client.get("/api/catalog/search", params={"q": "набережная Иртыша"})
    assert r.status_code == 200
    assert r.json()["total"] >= 1
    # 2. фильтр: фото 1960-х, место — Усть-Каменогорск
    r = await client.get(
        "/api/catalog/search",
        params={
            "q": "набережная",
            "category": "photo",
            "period_from": 1960,
            "period_to": 1969,
            "place": "Усть-Каменогорск",
        },
    )
    body = r.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["file_access"] == "open" and item["has_digital_copy"] and item["thumb_url"]
    assert item["is_demo"] is True
    # 3. карточка со всеми полями ТЗ §5.3
    card = (await client.get(f"/api/catalog/documents/{item['id']}")).json()
    for field in ("title", "cipher", "fund", "inventory", "case", "period_label", "summary", "doc_type",
                  "language", "sheets_count", "storage_location", "file_access", "has_digital_copy"):  # fmt: skip
        assert card[field] not in (None, ""), field
    assert card["fund"]["number"] == "Р-101"
    # 4. просмотр открытого скана
    assert card["pages"], "у открытого документа должна быть облегчённая копия"
    img = await client.get(card["pages"][0]["url"])
    assert img.status_code == 200
    assert img.headers["content-type"] == "image/webp"
    assert img.headers["x-content-type-options"] == "nosniff"


async def test_closed_file_denied_everywhere(
    client: AsyncClient, session: AsyncSession, seeded: dict[str, Any]
) -> None:
    doc_id = seeded["keys"]["personnel-1950"]
    # описание публично → карточка открывается, но без страниц и с условиями доступа
    card = (await client.get(f"/api/catalog/documents/{doc_id}")).json()
    assert card["file_access"] == "closed"
    assert card["pages"] == []
    assert card["has_digital_copy"] is True
    assert card["access_conditions"]
    # прямые ссылки на любые копии закрытого документа → 403
    files = await _files(session, doc_id)
    assert set(files) == {"master", "view", "thumb"}
    for f in files.values():
        r = await client.get(f"/api/media/{f.id}")
        assert r.status_code == 403, f.kind
        assert r.headers["content-type"].startswith("application/json")
    # в выдаче поиска миниатюры нет
    r = await client.get("/api/catalog/search", params={"q": "личные дела"})
    closed = [i for i in r.json()["items"] if i["id"] == str(doc_id)]
    assert closed and closed[0]["thumb_url"] is None


async def test_restricted_file_denied(client: AsyncClient, session: AsyncSession, seeded: dict[str, Any]) -> None:
    doc_id = seeded["keys"]["genplan-1958"]
    files = await _files(session, doc_id)
    assert (await client.get(f"/api/media/{files['view'].id}")).status_code == 403


async def test_master_copy_never_public(client: AsyncClient, session: AsyncSession, seeded: dict[str, Any]) -> None:
    files = await _files(session, seeded["keys"]["photo-embankment-1965"])
    assert (await client.get(f"/api/media/{files['view'].id}")).status_code == 200
    assert (await client.get(f"/api/media/{files['master'].id}")).status_code == 403


@pytest.mark.parametrize("key", ["hidden-cards-1950", "edu-1967-hidden", "ridder-mine-1930"])
async def test_hidden_and_review_not_exposed(
    key: str, client: AsyncClient, session: AsyncSession, seeded: dict[str, Any]
) -> None:
    doc_id = seeded["keys"][key]
    assert (await client.get(f"/api/catalog/documents/{doc_id}")).status_code == 404
    for f in (await _files(session, doc_id)).values():
        assert (await client.get(f"/api/media/{f.id}")).status_code == 404
    assert await session.get(SearchIndex, doc_id) is None


HIDDEN_KEYS = ("hidden-cards-1950", "hidden-cards-1956", "edu-1967-hidden", "ridder-mine-1930")


@pytest.mark.parametrize("q", ["секретныйтест", "СЛУЖЕБНОЕ ОПИСАНИЕ", "Личные карточки работников", "горных выработок"])
async def test_hidden_text_absent_from_search(q: str, client: AsyncClient, seeded: dict[str, Any]) -> None:
    hidden = {str(seeded["keys"][k]) for k in HIDDEN_KEYS}
    for params in ({"q": q}, {"title": q}, {"q": q, "page_size": 50}):
        items = (await client.get("/api/catalog/search", params=params)).json()["items"]
        leaked = [i for i in items if i["id"] in hidden or "СЛУЖЕБНОЕ" in (i["summary"] or "")]
        assert not leaked, (params, leaked)
    assert (await client.get("/api/catalog/search", params={"q": "секретныйтест"})).json()["total"] == 0


async def test_hidden_inventory_and_case_not_exposed(
    client: AsyncClient, session: AsyncSession, seeded: dict[str, Any]
) -> None:
    doc = await session.get(Document, seeded["keys"]["hidden-cards-1950"])
    assert doc is not None
    assert (await client.get(f"/api/catalog/inventories/{doc.inventory_id}")).status_code == 404
    assert (await client.get(f"/api/catalog/cases/{doc.case_id}")).status_code == 404
    fund = (await client.get(f"/api/catalog/funds/{doc.fund_id}")).json()
    assert all(ch["id"] != str(doc.inventory_id) for ch in fund["children"])


async def test_hierarchy_navigation(client: AsyncClient, seeded: dict[str, Any]) -> None:
    funds = (await client.get("/api/catalog/funds")).json()
    fund = next(f for f in funds if f["number"] == "Р-245")
    node = (await client.get(f"/api/catalog/funds/{fund['id']}")).json()
    inv = node["children"][0]
    node = (await client.get(f"/api/catalog/inventories/{inv['id']}")).json()
    assert node["parents"][0]["number"] == "Р-245"
    case = next(c for c in node["children"] if c["number"] == "5")
    node = (await client.get(f"/api/catalog/cases/{case['id']}")).json()
    assert [p["number"] for p in node["parents"]] == ["Р-245", "1"]
    assert {d["id"] for d in node["documents"]} >= {str(seeded["keys"]["order-zinc-1952"])}


async def test_personal_funds_entry_point(client: AsyncClient) -> None:
    funds = (await client.get("/api/catalog/funds", params={"personal": True})).json()
    assert [f["number"] for f in funds] == ["Л-15"]
    r = (await client.get("/api/catalog/search", params={"personal": True})).json()
    assert r["total"] >= 5 and all(i["is_personal_fund"] for i in r["items"])


async def test_unpublishing_removes_from_index(
    client: AsyncClient, session: AsyncSession, seeded: dict[str, Any]
) -> None:
    doc_id = seeded["keys"]["school-1965"]
    backend = get_search_backend()
    try:
        await session.execute(update(Document).where(Document.id == doc_id).values(description_status="hidden"))
        assert await backend.index_document(session, doc_id) is False
        await session.commit()
        items = (await client.get("/api/catalog/search", params={"q": "школа № 24"})).json()["items"]
        assert str(doc_id) not in {i["id"] for i in items}
        assert (await client.get(f"/api/catalog/documents/{doc_id}")).status_code == 404
    finally:
        await session.execute(update(Document).where(Document.id == doc_id).values(description_status="public"))
        assert await backend.index_document(session, doc_id) is True
        await session.commit()


async def test_unknown_status_rejected_by_db(session: AsyncSession, seeded: dict[str, Any]) -> None:
    with pytest.raises(IntegrityError):
        await session.execute(
            update(Document).where(Document.id == seeded["keys"]["school-1965"]).values(file_access="maybe")
        )
    await session.rollback()


async def test_synonyms_and_variants(client: AsyncClient) -> None:
    base = (await client.get("/api/catalog/search", params={"q": "Усть-Каменогорск фото"})).json()["total"]
    for q in ("Өскемен фото", "Oskemen photo", "Ust-Kamenogorsk фотография"):
        r = (await client.get("/api/catalog/search", params={"q": q})).json()
        assert r["total"] == base, q
        assert "ust-kamenogorsk" in r["expanded_terms"]
    old = (await client.get("/api/catalog/search", params={"q": "Риддер"})).json()
    assert old["total"] >= 3 and "ridder" in old["expanded_terms"]


async def test_typo_tolerant_search(client: AsyncClient) -> None:
    r = (await client.get("/api/catalog/search", params={"q": "фотограифи"})).json()
    assert r["total"] >= 1 and r["fuzzy"] is True


async def test_empty_result_is_ok(client: AsyncClient) -> None:
    r = await client.get("/api/catalog/search", params={"q": "космический корабль марсианской экспедиции 2099"})
    assert r.status_code == 200 and r.json()["total"] == 0 and r.json()["items"] == []


async def test_translation_fallback(client: AsyncClient, seeded: dict[str, Any]) -> None:
    doc_id = seeded["keys"]["school-1965"]  # только ru
    card = (await client.get(f"/api/catalog/documents/{doc_id}", params={"lang": "kk"})).json()
    assert card["translation"] == {
        "requested_lang": "kk",
        "lang": "ru",
        "status": "missing",
        "is_fallback": True,
    }
    kk_original = (
        await client.get(f"/api/catalog/documents/{seeded['keys']['news-1991-indep']}", params={"lang": "kk"})
    ).json()
    assert kk_original["translation"]["status"] == "original"


async def test_no_static_mount_for_storage() -> None:
    app = create_app()
    assert not [r for r in app.routes if isinstance(r, Mount)], "файлы хранилища нельзя монтировать как статику"


def test_storage_path_traversal_blocked() -> None:
    with pytest.raises(PermissionError):
        storage.resolve("../../etc/passwd")


def test_upload_signature_check() -> None:
    with pytest.raises(storage.UnsupportedFile):
        storage.sniff_mime(b"<html><script>alert(1)</script></html>")
    assert storage.sniff_mime(b"%PDF-1.7 ...") == "application/pdf"
