"""Сценарий 3 (Д §6 «Информация об услугах») + CMS: страницы, новости, FAQ, отзывы, санитизация."""

from __future__ import annotations

from httpx import AsyncClient
from starlette.routing import Route

from app.cms.sanitize import clean_html
from app.core.ratelimit import limiter
from app.main import create_app

# Единственные пути, где допустима запись извне (админка — этап 5, помощник — этап 6, отзыв — не обращение)
ALLOWED_WRITE_PREFIXES = ("/api/admin", "/api/auth", "/api/feedback", "/api/assistant")
FORBIDDEN_WORDS = ("order", "cart", "basket", "payment", "checkout", "application", "zayav", "zakaz", "oplat")


def test_no_order_or_payment_endpoints() -> None:
    app = create_app()
    for r in app.routes:
        if not isinstance(r, Route):
            continue
        path = r.path.lower()
        assert not any(w in path for w in FORBIDDEN_WORDS), f"подозрительный маршрут {path}"
        writes = (r.methods or set()) & {"POST", "PUT", "PATCH", "DELETE"}
        if writes:
            assert path.startswith(ALLOWED_WRITE_PREFIXES), f"{writes} {path} — запись вне разрешённых разделов"


async def test_paid_services_price_list_and_pdf(client: AsyncClient) -> None:
    page = (await client.get("/api/pages/services-paid")).json()
    assert page["title"] == "Платные услуги"
    assert page["actualized_at"]
    act = page["data"]["act"]
    assert act["number"] == "289" and act["date"] == "2023-12-15"
    sections = {s["no"]: s for s in page["data"]["sections"]}
    copies = {r["index"]: r for r in sections["8"]["rows"]}
    assert copies["8.1.1.1.5."]["price"] == "219,0"
    assert "сверяйте с PDF" in page["data"]["transcription_note"]
    pdfs = [a for a in page["attachments"] if a["kind"] == "pdf"]
    assert {a["lang"] for a in pdfs} == {"ru", "kk"}
    for a in pdfs:
        r = await client.get(a["url"])
        assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
        assert r.content[:5] == b"%PDF-"
    externals = [a for a in page["attachments"] if a["external"]]
    assert externals and all(a["url"].startswith("https://") for a in externals)


async def test_state_service_has_external_channels(client: AsyncClient) -> None:
    page = (await client.get("/api/pages/services-state")).json()
    urls = {a["url"] for a in page["attachments"] if a["external"]}
    assert {"https://egov.kz", "https://eotinish.kz"} <= urls
    assert "заявления не принимаются" in page["body"]
    assert page["is_demo"] is True


async def test_public_docs_allowlist(client: AsyncClient) -> None:
    assert (await client.get("/api/public-docs/compliance-plan-ru")).status_code == 200
    for key in ("unknown", "..%2F..%2Fpyproject.toml", "scan_142"):
        assert (await client.get(f"/api/public-docs/{key}")).status_code == 404


async def test_legal_acts_marked_unverified(client: AsyncClient) -> None:
    page = (await client.get("/api/pages/services-legal")).json()
    acts = page["data"]["acts"]
    assert len(acts) >= 6
    assert any(not a["verified"] for a in acts), "непроверенные ссылки должны быть помечены"


async def test_page_translation_fallback_keeps_translated_title(client: AsyncClient) -> None:
    page = (await client.get("/api/pages/about-history", params={"lang": "kk"})).json()
    assert page["title"] == "Архив тарихы"
    assert page["translation"]["is_fallback"] is True and page["translation"]["lang"] == "ru"
    nav = (await client.get("/api/pages", params={"section": "services", "lang": "kk"})).json()
    assert "Ақылы қызметтер" in [p["title"] for p in nav]


async def test_unknown_page_404(client: AsyncClient) -> None:
    assert (await client.get("/api/pages/does-not-exist")).status_code == 404


async def test_news_list_filter_detail(client: AsyncClient) -> None:
    lst = (await client.get("/api/news", params={"page_size": 30})).json()
    # 6 демо-новостей из сида (другие тесты могут добавить свои опубликованные)
    assert sum(1 for i in lst["items"] if i["is_demo"]) >= 6 or lst["total"] >= 6
    dates = [i["published_at"] for i in lst["items"] if i["published_at"]]
    assert dates == sorted(dates, reverse=True)
    assert (await client.get("/api/news", params={"category": "exhibition"})).json()["total"] == 1
    assert (await client.get("/api/news", params={"q": "читального"})).json()["total"] == 1
    demo = next(i for i in lst["items"] if i["is_demo"])
    item = (await client.get(f"/api/news/{demo['slug']}")).json()
    assert item["body"] and "related" in item
    cover = item["cover_url"]
    assert cover and (await client.get(cover)).status_code == 200


async def test_faq_grouped(client: AsyncClient) -> None:
    groups = (await client.get("/api/faq", params={"lang": "en"})).json()
    assert [g["slug"] for g in groups] == ["catalog", "services", "visit", "site"]
    assert groups[0]["title"] == "Online catalogue"


async def test_feedback_validation_and_rate_limit(client: AsyncClient) -> None:
    limiter.reset()
    ok = await client.post("/api/feedback", json={"message": "Удобный каталог, спасибо!", "page": "/ru/catalog"})
    assert ok.status_code == 201
    assert "не официальное обращение" in ok.json()["notice"]
    bad = await client.post("/api/feedback", json={"message": "Добавьте фото", "email": "a@b.kz"})
    assert bad.status_code == 422, "email без согласия на обработку ПДн"
    assert (await client.post("/api/feedback", json={"message": "коротко"})).status_code == 422
    codes = [
        (await client.post("/api/feedback", json={"message": f"Отзыв номер {i} о работе сайта"})).status_code
        for i in range(6)
    ]
    assert 429 in codes
    limiter.reset()


def test_html_sanitizer() -> None:
    dirty = '<p onclick="x()">ok<script>alert(1)</script><a href="javascript:alert(1)">x</a><a href="https://egov.kz">e</a></p>'
    out = clean_html(dirty) or ""
    assert "<script" not in out and "onclick" not in out and "javascript:" not in out
    assert 'rel="noopener noreferrer"' in out and 'target="_blank"' in out
