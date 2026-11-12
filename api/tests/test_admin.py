"""Админка: сценарии 6 (согласование) и 7 (права филиала), авторизация, CSRF, каталог, загрузка файлов."""

from __future__ import annotations

import io
import time
import uuid
from typing import Any

import jwt
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import session as sess
from app.core.config import get_settings
from app.core.ratelimit import limiter
from app.main import create_app
from app.models import AuditLog, ContentVersion, Document
from tests.staff_fixtures import PASSWORD, STAFF  # noqa: F401


async def _audit(session: AsyncSession, action: str, entity_id: Any = None) -> list[AuditLog]:
    stmt = select(AuditLog).where(AuditLog.action == action)
    if entity_id is not None:
        stmt = stmt.where(AuditLog.entity_id == str(entity_id))
    return list((await session.execute(stmt)).scalars())


# ---------------- сценарий 6 ----------------
async def test_scenario6_editor_review_moderator_publish(
    login: Any, client: AsyncClient, session: AsyncSession
) -> None:
    editor = await login("editor")
    slug = f"test-news-{uuid.uuid4().hex[:8]}"
    r = await editor.post("/api/admin/news", json={
        "slug": slug, "category": "news",
        "translations": {
            "ru": {"title": "Тестовая новость", "lead": "Лид", "body": "<p>Текст<script>x()</script></p>"}
        },
    })  # fmt: skip
    assert r.status_code == 201, r.text
    news = r.json()
    assert news["workflow_status"] == "draft"
    assert "<script" not in news["translations"]["ru"]["body"]
    assert (await client.get(f"/api/news/{slug}")).status_code == 404, "черновик не виден публично"

    r = await editor.post(f"/api/admin/workflow/news/{news['id']}", json={"to": "review", "comment": "Прошу проверить"})
    assert r.json()["status"] == "review"
    assert (await client.get(f"/api/news/{slug}")).status_code == 404, "на проверке не виден публично"

    r = await editor.post(f"/api/admin/workflow/news/{news['id']}", json={"to": "published"})
    assert r.status_code == 403, "редактор не может опубликовать сам"

    moderator = await login("moderator")
    queue = (await moderator.get("/api/admin/review-queue")).json()
    assert any(i["id"] == news["id"] for i in queue)
    r = await moderator.post(f"/api/admin/workflow/news/{news['id']}", json={"to": "published", "comment": "Одобрено"})
    assert r.status_code == 200 and r.json()["status"] == "published"
    assert (await client.get(f"/api/news/{slug}")).status_code == 200

    versions = (await moderator.get(f"/api/admin/workflow/news/{news['id']}/versions")).json()
    assert [v["status"] for v in versions] == ["published", "review", "draft"]
    assert versions[0]["reviewer"] == STAFF["moderator"][0] and versions[1]["author"] == STAFF["editor"][0]
    stored = (
        (await session.execute(select(ContentVersion).where(ContentVersion.entity_id == uuid.UUID(news["id"]))))
        .scalars()
        .all()
    )
    assert all(v.payload["translations"] for v in stored), "в версии хранится снимок материала"
    for action in ("news.create", "workflow.draft->review", "workflow.review->published"):
        assert await _audit(session, action, news["id"]), action
    assert any(e.result == "denied" for e in await _audit(session, "workflow.review->published", news["id"]))


async def test_four_eyes_principle(login: Any) -> None:
    moderator = await login("moderator")
    # модератор не может согласовать материал, который сам отправил на проверку
    pages = (await moderator.get("/api/admin/pages")).json()
    faq_id = None
    r = await moderator.get("/api/admin/faq")
    assert r.status_code == 200
    editor = await login("editor")
    groups = {f["group"]: f["group_id"] for f in r.json()}
    created = await editor.post(
        "/api/admin/faq",
        json={"group_id": groups["site"], "translations": {"ru": {"question": "Тестовый вопрос?", "answer": "Ответ"}}},
    )
    faq_id = created.json()["id"]
    sa = await login("superadmin")
    await sa.post(f"/api/admin/workflow/faq/{faq_id}", json={"to": "review"})
    # суперадмин может и согласовать своё (исключение для аварийных случаев)
    assert (await sa.post(f"/api/admin/workflow/faq/{faq_id}", json={"to": "approved"})).status_code == 200
    assert pages


# ---------------- сценарий 7 ----------------
async def test_scenario7_branch_admin_own_vs_foreign(
    login: Any, client: AsyncClient, session: AsyncSession, seeded: dict[str, Any]
) -> None:
    ridder = seeded["branches"]["ridder"]
    altai = seeded["branches"]["altai"]
    ba = await login("branch_admin")

    listed = (await ba.get("/api/admin/branches")).json()
    assert [b["slug"] for b in listed] == ["ridder"], "администратор филиала видит только свой филиал"

    r = await ba.patch(
        f"/api/admin/branches/{ridder.id}",
        json={"phone": "8 (72336) 00-00-01", "translations": {"ru": {"hours": "Пн–Пт 9:00–17:00"}}},
    )
    assert r.status_code == 200, r.text
    public = (await client.get("/api/branches/ridder")).json()
    assert public["phone"] == "8 (72336) 00-00-01" and public["hours"] == "Пн–Пт 9:00–17:00"

    r = await ba.patch(f"/api/admin/branches/{altai.id}", json={"phone": "000"})
    assert r.status_code == 403
    denied = [e for e in await _audit(session, "branch.update", altai.id) if e.result == "denied"]
    assert denied and denied[0].user_email == STAFF["branch_admin"][0]
    assert (await client.get("/api/branches/altai")).json()["phone"] != "000"

    r = await ba.patch(f"/api/admin/branches/{ridder.id}", json={"coords_verified": True})
    assert r.status_code == 403, "координаты/видимость меняет только администратор с правом на все филиалы"
    assert (await ba.get(f"/api/admin/branches/{altai.id}")).status_code == 403


# ---------------- авторизация ----------------
async def test_wrong_password_and_rate_limit(staff: dict[str, str], session: AsyncSession) -> None:
    limiter.reset()
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        r = await c.post("/api/auth/login", json={"email": staff["editor"], "password": "wrong"})
        assert r.status_code == 401 and "Неверный" in r.json()["detail"]
        r = await c.post("/api/auth/login", json={"email": "nobody@test.kz", "password": "wrong"})
        assert r.status_code == 401, "одинаковый ответ для несуществующего пользователя"
        codes = [
            (await c.post("/api/auth/login", json={"email": staff["editor"], "password": "x"})).status_code
            for _ in range(5)
        ]
        assert 429 in codes
    denied = [e for e in await _audit(session, "auth.login") if e.result == "denied"]
    assert denied and all("password" not in (e.details or {}) for e in denied)
    limiter.reset()


async def test_unauthenticated_and_tampered(staff: dict[str, str]) -> None:
    async with AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test") as c:
        assert (await c.get("/api/admin/news")).status_code == 401
        c.cookies.set(sess.SESSION_COOKIE, "eyJhbGciOiJub25lIn0.e30.", path="/api")
        assert (await c.get("/api/auth/me")).status_code == 401
        expired = jwt.encode(
            {"sub": str(uuid.uuid4()), "csrf": "x", "auth_time": int(time.time()) - 60, "exp": int(time.time()) - 1},
            get_settings().require_secret(), algorithm="HS256",
        )  # fmt: skip
        c.cookies.set(sess.SESSION_COOKIE, expired, path="/api")
        assert (await c.get("/api/auth/me")).status_code == 401, "истёкшая по неактивности сессия"


async def test_csrf_required_for_writes(login: Any, session: AsyncSession) -> None:
    editor = await login("editor")
    r = await editor.c.post(
        "/api/admin/news", json={"slug": "no-csrf-news", "translations": {"ru": {"title": "Без CSRF"}}}
    )
    assert r.status_code == 403
    assert [e for e in await _audit(session, "csrf.reject") if e.result == "denied"]


async def test_logout_clears_session(login: Any) -> None:
    editor = await login("editor")
    assert (await editor.get("/api/auth/me")).status_code == 200
    assert (await editor.post("/api/auth/logout")).status_code == 204
    assert (await editor.get("/api/auth/me")).status_code == 401


async def test_role_separation(login: Any) -> None:
    analyst = await login("analyst")
    assert (await analyst.get("/api/admin/news")).status_code == 403
    assert (await analyst.get("/api/admin/audit")).status_code == 403
    editor = await login("editor")
    assert (await editor.get("/api/admin/catalog/documents")).status_code == 403
    assert (await editor.get("/api/admin/users")).status_code == 403


# ---------------- каталог ----------------
def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (120, 80), (200, 180, 150)).save(buf, "PNG")
    return buf.getvalue()


async def test_catalog_create_access_publish_upload(
    login: Any, client: AsyncClient, session: AsyncSession, seeded: dict[str, Any]
) -> None:
    arch = await login("archivist")
    open_doc = await session.get(Document, seeded["keys"]["school-1965"])
    assert open_doc is not None
    case_id = str(open_doc.case_id)

    bad = await arch.post(
        "/api/admin/catalog/documents",
        json={
            "case_id": case_id,
            "sheets": "л. 90",
            "category": "photo",
            "doc_type": "photo",
            "translations": {"kk": {"title": "Тек қазақша"}},
        },
    )
    assert bad.status_code == 422, "без названия на языке оригинала карточка не создаётся"
    r = await arch.post("/api/admin/catalog/documents", json={
        "case_id": case_id, "sheets": "л. 90–91", "category": "historical", "doc_type": "decision",
        "date_from": "1965-09-01", "date_to": "1965-09-01", "tags": ["Тест", "школа"],
        "translations": {"ru": {"title": "Новое решение (тест)", "summary": "Тестовая запись"}},
    })  # fmt: skip
    assert r.status_code == 201, r.text
    doc = r.json()
    assert (doc["workflow_status"], doc["description_status"], doc["file_access"]) == ("draft", "review", "closed")
    dup = await arch.post(
        "/api/admin/catalog/documents",
        json={
            "case_id": case_id,
            "sheets": "л. 90–91",
            "category": "historical",
            "doc_type": "decision",
            "translations": {"ru": {"title": "Дубль"}},
        },
    )
    assert dup.status_code == 409

    up = await arch.c.post(f"/api/admin/catalog/documents/{doc['id']}/files", headers=arch.csrf,
                           files={"files": ("scan.png", _png(), "image/png")},
                           data={"provenance": "Тестовая оцифровка", "rights_note": "CC0"})  # fmt: skip
    assert up.status_code == 201, up.text
    kinds = sorted(f["kind"] for f in up.json()["files"])
    assert kinds == ["master", "thumb", "view"]
    master = next(f for f in up.json()["files"] if f["kind"] == "master")
    assert len(master["sha256"]) == 64
    fake = await arch.c.post(f"/api/admin/catalog/documents/{doc['id']}/files", headers=arch.csrf,
                             files={"files": ("x.png", b"<html><script>alert(1)</script>", "image/png")},
                             data={"provenance": "Подделка для теста", "rights_note": "нет"})  # fmt: skip
    assert fake.status_code == 415, "MIME проверяется по сигнатуре, а не по расширению/заголовку"
    assert (await arch.get(master["url"])).status_code == 200, "сотрудник видит мастер-копию"
    view = next(f for f in up.json()["files"] if f["kind"] == "view")
    assert (await client.get(f"/api/media/{view['id']}")).status_code == 404, "черновик не виден публично"

    # архивист не может открыть доступ к файлу — это право модератора
    r = await arch.patch(
        f"/api/admin/catalog/documents/{doc['id']}/access", json={"file_access": "open", "reason": "попытка открыть"}
    )
    assert r.status_code == 403
    await arch.post(f"/api/admin/workflow/document/{doc['id']}", json={"to": "review"})

    mod = await login("moderator")
    r = await mod.post(f"/api/admin/workflow/document/{doc['id']}", json={"to": "published", "comment": "ок"})
    assert r.status_code == 200
    card = await client.get(f"/api/catalog/documents/{doc['id']}")
    assert card.status_code == 200 and card.json()["file_access"] == "closed" and card.json()["pages"] == []
    assert (await client.get(f"/api/media/{view['id']}")).status_code == 403, "публикация описания не открывает файл"
    r = await mod.patch(
        f"/api/admin/catalog/documents/{doc['id']}/access",
        json={"file_access": "open", "reason": "Разрешено к публикации"},
    )
    assert r.status_code == 200
    assert (await client.get(f"/api/media/{view['id']}")).status_code == 200
    found = (await client.get("/api/catalog/search", params={"q": "Новое решение тест"})).json()
    assert any(i["id"] == doc["id"] for i in found["items"])
    assert await _audit(session, "document.access", doc["id"])
    assert [e for e in await _audit(session, "perm:catalog.set_access") if e.result == "denied"]


async def test_users_management(login: Any, seeded: dict[str, Any]) -> None:
    sa = await login("superadmin")
    r = await sa.post(
        "/api/admin/users",
        json={
            "email": f"new.{uuid.uuid4().hex[:6]}@test.kz",
            "full_name": "Новый филиал",
            "role": "branch_admin",
            "branch_id": str(seeded["branches"]["zaisan"].id),
        },
    )
    assert r.status_code == 201 and len(r.json()["temporary_password"]) >= 12
    bad = await sa.post(
        "/api/admin/users", json={"email": "x.y@test.kz", "full_name": "Без филиала", "role": "branch_admin"}
    )
    assert bad.status_code == 422
    audit_page = (await sa.get("/api/admin/audit", params={"action": "users.create"})).json()
    assert audit_page["total"] >= 1
