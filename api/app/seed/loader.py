"""Загрузка демо-данных. Полностью пересоздаёт контент (прототип), пароли демо-учёток генерирует заново."""

from __future__ import annotations

import json
import secrets
import shutil
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.passwords import hash_password
from app.auth.permissions import PERMISSIONS, ROLE_NAMES, ROLE_PERMISSIONS
from app.cms.sanitize import clean_html
from app.core.config import get_settings
from app.media import storage
from app.models import (
    ArchiveCase,
    Base,
    Branch,
    BranchTranslation,
    CaseTranslation,
    Collection,
    CollectionItem,
    CollectionTranslation,
    DigitalFile,
    Document,
    DocumentTranslation,
    Event,
    EventTranslation,
    Exhibit,
    Exhibition,
    ExhibitionTranslation,
    ExhibitTranslation,
    Faq,
    FaqGroup,
    FaqGroupTranslation,
    FaqTranslation,
    Fund,
    FundTranslation,
    Inventory,
    InventoryTranslation,
    MemorialDate,
    MemorialDateTranslation,
    News,
    NewsTranslation,
    Page,
    PageTranslation,
    Permission,
    Person,
    PersonTranslation,
    Role,
    RolePermission,
    Synonym,
    User,
    UserRole,
)
from app.search.postgres import get_search_backend
from app.search.synonyms import DEFAULT_SYNONYMS
from app.seed.images import render, render_photo

LANGS = ("ru", "kk", "en")


@dataclass
class Credential:
    role: str
    email: str
    password: str
    branch: str | None = None


def seed_dir() -> Path:
    return Path(get_settings().seed_dir)


def _load(name: str) -> Any:
    return json.loads((seed_dir() / name).read_text(encoding="utf-8"))


def _image(kind: str, key: str, title: str, page: int = 1) -> tuple[bytes, str, str]:
    """(jpeg, provenance, rights): реальное фото из seed/photos/photos.json по ключу, иначе заглушка Pillow."""
    photos = seed_dir() / "photos"
    meta = (
        json.loads((photos / "photos.json").read_text(encoding="utf-8")) if (photos / "photos.json").is_file() else {}
    )
    ph = meta.get(key) if page == 1 else None
    if not ph:
        return (
            render(kind, key, title, page),
            "Сгенерированная демонстрационная заглушка (Pillow), не архивный документ",
            "CC0 (сгенерировано)",
        )
    credit = f"Фото: {ph['author']} · {ph['license']} · Wikimedia Commons"
    return (
        render_photo(photos / ph["file"], credit),
        f"{credit} ({ph['source']}). Современный снимок для демонстрации, не архивный документ",
        f"{ph['license']} ({ph['license_url']}); изменено: уменьшено, добавлена подпись",
    )


async def reset(session: AsyncSession) -> None:
    tables = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
    await session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))  # имена из метаданных, не из ввода
    root = storage.root()
    for sub in ("master", "view", "thumb"):
        target = (root / sub).resolve()
        if target.parent == root and target.exists():
            shutil.rmtree(target)


async def seed_roles(session: AsyncSession) -> dict[str, Role]:
    perms = {code: Permission(code=code, description=desc) for code, desc in PERMISSIONS.items()}
    session.add_all(perms.values())
    roles = {code: Role(code=code, name=name) for code, name in ROLE_NAMES.items()}
    session.add_all(roles.values())
    await session.flush()
    for code, role in roles.items():
        for p in ROLE_PERMISSIONS[code]:
            session.add(RolePermission(role_id=role.id, permission_id=perms[p].id))
    return roles


async def create_user(
    session: AsyncSession,
    roles: dict[str, Role],
    role: str,
    email: str,
    password: str,
    branch: Branch | None = None,
    full_name: str | None = None,
) -> User:
    user = User(email=email, full_name=full_name or ROLE_NAMES[role], password_hash=hash_password(password))
    session.add(user)
    await session.flush()
    session.add(
        UserRole(user_id=user.id, role_id=roles[role].id, role_code=role, branch_id=branch.id if branch else None)
    )
    return user


async def seed_users(session: AsyncSession, roles: dict[str, Role], branches: dict[str, Branch]) -> list[Credential]:
    creds: list[Credential] = []
    plan: list[tuple[str, str, str | None]] = [
        ("superadmin", "superadmin@demo.vko-archive.kz", None),
        ("site_admin", "siteadmin@demo.vko-archive.kz", None),
        ("editor", "editor@demo.vko-archive.kz", None),
        ("archivist", "archivist@demo.vko-archive.kz", None),
        ("moderator", "moderator@demo.vko-archive.kz", None),
        ("analyst", "analyst@demo.vko-archive.kz", None),
        ("branch_admin", "branch.ridder@demo.vko-archive.kz", "ridder"),
        ("branch_admin", "branch.altai@demo.vko-archive.kz", "altai"),
    ]
    for role, email, branch_slug in plan:
        password = get_settings().demo_password.get_secret_value() or secrets.token_urlsafe(12)
        branch = branches[branch_slug] if branch_slug else None
        name = f"{ROLE_NAMES[role]} (демо)" + (f" — {branch_slug}" if branch_slug else "")
        await create_user(session, roles, role, email, password, branch, name)
        creds.append(Credential(role, email, password, branch_slug))
    return creds


async def seed_branches(session: AsyncSession) -> dict[str, Branch]:
    out: dict[str, Branch] = {}
    for i, b in enumerate(_load("branches.json")):
        branch = Branch(
            slug=b["slug"],
            type=b["type"],
            official_name=b.get("official_name_ru") or b["name"]["ru"],
            director=b.get("director"),
            phone=b.get("phone"),
            phones_extra=b.get("phones_extra"),
            email=b.get("email"),
            lat=b.get("lat"),
            lon=b.get("lon"),
            coords_verified=bool(b.get("coords_verified")),
            hours_verified=bool(b.get("hours_verified", b["type"] == "main")),
            visible=True,
            sort_order=i,
            source=b.get("source"),
        )
        for lang in LANGS:
            branch.translations.append(
                BranchTranslation(
                    lang=lang,
                    translation_status=b["translation_status"][lang],
                    name=b["name"][lang],
                    short_name=b["short_name"][lang],
                    locality=b["locality"][lang],
                    address=b["address"][lang],
                    hours=b["hours"][lang],
                )
            )
        session.add(branch)
        out[branch.slug] = branch
    await session.flush()
    return out


async def seed_memorial_dates(session: AsyncSession) -> int:
    items = _load("memorial_dates.json")
    for it in items:
        md = MemorialDate(ext_id=it["id"], year=it["year"], month=it["month"], day=it["day"], source=it["source"])
        for lang in ("ru", "kk"):
            if it["title"][lang]:
                md.translations.append(
                    MemorialDateTranslation(
                        lang=lang,
                        translation_status="original",
                        date_label=it["date_label"][lang],
                        title=it["title"][lang],
                    )
                )
        session.add(md)
    return len(items)


async def seed_synonyms(session: AsyncSession) -> None:
    seen: set[str] = set()
    for key, terms in DEFAULT_SYNONYMS.items():
        for term in terms:
            if term.lower() not in seen:
                seen.add(term.lower())
                session.add(Synonym(group_key=key, term=term))


def _tr_rows(model: type[Any], original: str, fields: dict[str, dict[str, str] | None], required: str) -> list[Any]:
    """Строки переводов из словарей {lang: text}. Язык оригинала — original, остальные — machine."""
    langs = [lang for lang in LANGS if lang in (fields[required] or {})]
    rows = []
    for lang in langs:
        values = {name: (vals or {}).get(lang) for name, vals in fields.items()}
        rows.append(model(lang=lang, translation_status="original" if lang == original else "machine", **values))
    return rows


def _year(d: str | None) -> int | None:
    return int(d[:4]) if d else None


async def _attach_images(
    session: AsyncSession, doc: Document, key: str, kind: str, title: str, pages: int, with_images: bool
) -> None:
    if not with_images:
        return
    for page in range(1, pages + 1):
        data, provenance, rights = _image(kind, key, title, page)
        master = storage.store_master(data)
        view, thumb = storage.store_derivatives(data)
        m = DigitalFile(
            document_id=doc.id,
            kind="master",
            page_no=page,
            storage_key=master.storage_key,
            mime=master.mime,
            size=master.size,
            sha256=master.sha256,
            width=master.width,
            height=master.height,
            original_filename=f"demo-{page}.jpg",
            provenance=provenance,
            rights_note=rights,
            is_demo=True,
        )
        session.add(m)
        await session.flush()
        for st, k in ((view, "view"), (thumb, "thumb")):
            session.add(
                DigitalFile(
                    document_id=doc.id,
                    parent_id=m.id,
                    kind=k,
                    page_no=page,
                    storage_key=st.storage_key,
                    mime=st.mime,
                    size=st.size,
                    sha256=st.sha256,
                    width=st.width,
                    height=st.height,
                    provenance=provenance,
                    rights_note=rights,
                    is_demo=True,
                )
            )


async def seed_catalog(
    session: AsyncSession, branches: dict[str, Branch], with_images: bool = True
) -> dict[str, uuid.UUID]:
    data = _load("catalog.json")
    keys: dict[str, uuid.UUID] = {}
    for fi, f in enumerate(data["funds"]):
        branch = branches[f["branch"]]
        fund_cipher = f"ГА ВКО Ф. {f['number']}"
        fund = Fund(
            number=f["number"],
            cipher=fund_cipher,
            year_from=f["years"][0],
            year_to=f["years"][1],
            is_personal_fund=f["personal"],
            branch_id=branch.id,
            description_status=f.get("status", "public"),
            workflow_status="published",
            is_demo=True,
        )
        fund.translations = _tr_rows(
            FundTranslation,
            "ru",
            {
                "title": f["title"],
                "historical_note": f.get("note"),
                "summary": None,
                "restricted_note": f.get("restricted_note"),
            },
            "title",
        )
        session.add(fund)
        await session.flush()
        for inv_data in f["inventories"]:
            inv_cipher = f"{fund_cipher} Оп. {inv_data['number']}"
            inv = Inventory(
                fund_id=fund.id,
                number=inv_data["number"],
                cipher=inv_cipher,
                year_from=inv_data["years"][0],
                year_to=inv_data["years"][1],
                description_status=inv_data.get("status", "public"),
                workflow_status="published",
                is_demo=True,
            )
            inv.translations = _tr_rows(
                InventoryTranslation, "ru", {"title": inv_data["title"], "summary": None}, "title"
            )
            session.add(inv)
            await session.flush()
            for c in inv_data["cases"]:
                case_cipher = f"{inv_cipher} Д. {c['number']}"
                case = ArchiveCase(
                    inventory_id=inv.id,
                    number=c["number"],
                    cipher=case_cipher,
                    year_from=c["years"][0],
                    year_to=c["years"][1],
                    sheets_count=c.get("sheets"),
                    description_status=c.get("status", "public"),
                    workflow_status="published",
                    is_demo=True,
                )
                case.translations = _tr_rows(CaseTranslation, "ru", {"title": c["title"], "summary": None}, "title")
                session.add(case)
                await session.flush()
                for di, d in enumerate(c["documents"]):
                    original = d.get("original_lang", "ru")
                    doc = Document(
                        case_id=case.id,
                        inventory_id=inv.id,
                        fund_id=fund.id,
                        fund_number=fund.number,
                        inventory_number=inv.number,
                        case_number=case.number,
                        cipher=f"{case_cipher} {d['sheets']}",
                        sheets=d["sheets"],
                        date_from=date.fromisoformat(d["date_from"]) if d.get("date_from") else None,
                        date_to=date.fromisoformat(d["date_to"]) if d.get("date_to") else None,
                        year_from=_year(d.get("date_from")),
                        year_to=_year(d.get("date_to")),
                        date_verified=d.get("date_verified", True),
                        category=d["category"],
                        doc_type=d["doc_type"],
                        language={"ru": "русский", "kk": "казахский"}.get(d["language"], d["language"]),
                        sheets_count=_sheet_count(d["sheets"]),
                        storage_location=f"{branch.slug}: хранилище № {fi + 1}, стеллаж {di + 1} (демо)",
                        branch_id=branch.id,
                        tags=d.get("tags", []),
                        is_personal_fund=f["personal"],
                        description_status=d.get("description_status", "public"),
                        file_access=d["file_access"],
                        workflow_status=d.get("workflow", "published"),
                        original_lang=original,
                        is_demo=True,
                    )
                    doc.translations = _tr_rows(
                        DocumentTranslation,
                        original,
                        {
                            "title": d["title"],
                            "summary": d.get("summary"),
                            "historical_note": d.get("note"),
                            "period_label": d.get("period"),
                            "author_org": d.get("author"),
                            "place": d.get("place"),
                            "topic": d.get("topic"),
                            "access_conditions": d.get("access"),
                        },
                        "title",
                    )
                    session.add(doc)
                    await session.flush()
                    keys[d["key"]] = doc.id
                    await _attach_images(
                        session,
                        doc,
                        d["key"],
                        d.get("image", "text"),
                        d["title"].get(original, ""),
                        d.get("pages", 1),
                        with_images,
                    )
    return keys


def _sheet_count(label: str) -> int | None:
    nums = [int(x) for x in "".join(ch if ch.isdigit() else " " for ch in label).split()]
    if not nums:
        return None
    return nums[-1] - nums[0] + 1 if len(nums) > 1 else 1


def _content(name: str) -> Any:
    return json.loads((seed_dir() / "content" / name).read_text(encoding="utf-8"))


def _status(lang: str, original: str, overrides: dict[str, str] | None) -> str:
    if lang == original:
        return "original"
    return (overrides or {}).get(lang, "machine")


async def seed_pages(session: AsyncSession) -> int:
    data = _content("pages.json")["pages"]
    pages_dir = seed_dir() / "content" / "pages"
    for i, p in enumerate(data):
        page = Page(
            slug=p["slug"],
            section=p["section"],
            sort_order=p.get("sort", i),
            actualized_at=datetime.fromisoformat(p["actualized_at"]).replace(tzinfo=UTC)
            if p.get("actualized_at")
            else None,
            attachments=p.get("attachments"),
            data=_content(p["data_file"]) if p.get("data_file") else p.get("data"),
            is_demo=bool(p.get("is_demo")),
            workflow_status="published",
        )
        bodies: dict[str, str] = dict(p.get("body") or {})
        for lang, fname in (p.get("body_file") or {}).items():
            bodies[lang] = (pages_dir / fname).read_text(encoding="utf-8")
        for lang, extra in (p.get("body_suffix") or {}).items():
            bodies[lang] = bodies.get(lang, "") + extra
        for lang in LANGS:
            title = p["title"].get(lang)
            if not title:
                continue
            body = bodies.get(lang)
            page.translations.append(
                PageTranslation(
                    lang=lang,
                    # тела на этом языке может не быть — тогда API отдаст тело оригинала с флагом фолбэка
                    translation_status=_status(lang, "ru", p.get("tr_status")),
                    title=title,
                    body=clean_html(body) if body else None,
                    meta_description=(p.get("meta") or {}).get(lang),
                )
            )
        session.add(page)
    return len(data)


async def seed_faq_news(session: AsyncSession, with_images: bool = True) -> tuple[int, int]:
    data = _content("faq_news.json")
    n_faq = 0
    for gi, g in enumerate(data["faq"]):
        group = FaqGroup(slug=g["slug"], sort_order=gi)
        group.translations = [
            FaqGroupTranslation(lang=lang, translation_status=_status(lang, "ru", None), title=t)
            for lang, t in g["title"].items()
        ]
        session.add(group)
        await session.flush()
        for ii, item in enumerate(g["items"]):
            faq = Faq(group_id=group.id, sort_order=ii, workflow_status="published")
            faq.translations = [
                FaqTranslation(
                    lang=lang, translation_status=_status(lang, "ru", None), question=q, answer=item["a"][lang]
                )
                for lang, q in item["q"].items()
                if item["a"].get(lang)
            ]
            session.add(faq)
            n_faq += 1
    for n in data["news"]:
        news = News(
            slug=n["slug"],
            category=n["category"],
            published_at=datetime.fromisoformat(n["date"]).replace(tzinfo=UTC),
            workflow_status="published",
            is_demo=True,
        )
        for lang, title in n["title"].items():
            body = (n.get("body") or {}).get(lang)
            news.translations.append(
                NewsTranslation(
                    lang=lang,
                    translation_status=_status(lang, "ru", None),
                    title=title,
                    lead=(n.get("lead") or {}).get(lang),
                    body=clean_html(body) if body else None,
                )
            )
        if with_images:
            news.cover_file_id = await _site_image(session, "photo", f"news:{n['slug']}", n["title"]["ru"])
        session.add(news)
    return n_faq, len(data["news"])


async def _site_image(session: AsyncSession, kind: str, key: str, title: str) -> uuid.UUID:
    """Изображение сайта (не документ каталога): мастер + облегчённая копия; возвращает id копии."""
    data, provenance, rights = _image(kind, key, title)
    master = storage.store_master(data)
    view, _thumb = storage.store_derivatives(data)
    m = DigitalFile(
        kind="master", storage_key=master.storage_key, mime=master.mime, size=master.size, sha256=master.sha256,
        width=master.width, height=master.height, provenance=provenance, rights_note=rights, is_demo=True,
    )  # fmt: skip
    session.add(m)
    await session.flush()
    v = DigitalFile(
        kind="view", parent_id=m.id, storage_key=view.storage_key, mime=view.mime, size=view.size, sha256=view.sha256,
        width=view.width, height=view.height, provenance=provenance, rights_note=rights, is_demo=True,
    )  # fmt: skip
    session.add(v)
    await session.flush()
    return v.id


def _trs(model: type[Any], values: dict[str, dict[str, Any]]) -> list[Any]:
    """{field: {lang: text}} -> строки переводов; язык оригинала ru, остальные machine."""
    first = next(iter(values.values()))
    langs = [lang for lang in LANGS if first.get(lang)]
    return [
        model(
            lang=lang,
            translation_status="original" if lang == "ru" else "machine",
            **{f: (v or {}).get(lang) for f, v in values.items()},
        )
        for lang in langs
    ]


async def seed_history(session: AsyncSession, keys: dict[str, uuid.UUID], with_images: bool = True) -> int:
    data = _content("history.json")
    ex = data["exhibition"]
    e = Exhibition(
        slug=ex["slug"],
        topic=ex["topic"],
        period_from=ex["period"][0],
        period_to=ex["period"][1],
        workflow_status="published",
        is_demo=True,
    )
    e.translations = _trs(
        ExhibitionTranslation, {"title": ex["title"], "summary": ex["summary"], "body": ex.get("body")}
    )
    session.add(e)
    await session.flush()
    for i, x in enumerate(ex["exhibits"]):
        doc_id = keys[x["doc"]]
        row = (
            await session.execute(
                select(DigitalFile.id, DigitalFile.rights_note)
                .where(DigitalFile.document_id == doc_id, DigitalFile.kind == "view")
                .order_by(DigitalFile.page_no)
            )
        ).first()
        view = row.id if row else None
        exhibit = Exhibit(
            exhibition_id=e.id,
            sort_order=i,
            document_id=doc_id,
            image_file_id=view,
            source_text="Демо-запись каталога ГА ВКО; источник изображения — в карточке документа",
            rights_note=row.rights_note if row else None,
        )
        exhibit.translations = _trs(ExhibitTranslation, {"caption": x["caption"], "description": x.get("desc")})
        session.add(exhibit)
        if i == 7:
            e.cover_file_id = view
    persons: dict[str, Person] = {}
    for pdata in data["persons"]:
        person = Person(
            slug=pdata["slug"],
            birth_label=pdata["birth"],
            death_label=pdata["death"],
            dates_verified=pdata["verified"],
            is_fictional=True,
            is_demo=True,
            workflow_status="published",
        )
        person.translations = _trs(
            PersonTranslation,
            {
                "name": pdata["name"],
                "role_line": pdata.get("role"),
                "bio": pdata.get("bio"),
                "source": pdata.get("source"),
            },
        )
        session.add(person)
        persons[pdata["slug"]] = person
    await session.flush()
    for c in data["collections"]:
        col = Collection(slug=c["slug"], topic=c["topic"], is_demo=True, workflow_status="published")
        col.translations = _trs(
            CollectionTranslation, {"title": c["title"], "summary": c.get("summary"), "editorial_note": c.get("note")}
        )
        order = 0
        for k in c["docs"]:
            col.items.append(CollectionItem(document_id=keys[k], sort_order=order))
            order += 1
        for ps in c.get("persons", []):
            col.items.append(CollectionItem(person_id=persons[ps].id, sort_order=order))
            order += 1
        session.add(col)
    for ev in data["events"]:
        event = Event(
            year=ev["year"],
            year_to=ev.get("year_to"),
            topic=ev["topic"],
            date_verified=ev["verified"],
            is_editorial=ev["editorial"],
            document_id=keys.get(ev["doc"]) if ev.get("doc") else None,
            workflow_status="published",
        )
        event.translations = _trs(
            EventTranslation,
            {
                "title": ev["title"],
                "description": ev.get("description"),
                "place": ev.get("place"),
                "source": ev.get("source"),
            },
        )
        session.add(event)
    return len(ex["exhibits"])


async def seed_all(session: AsyncSession, *, with_images: bool = True, with_users: bool = True) -> dict[str, Any]:
    await reset(session)
    roles = await seed_roles(session)
    branches = await seed_branches(session)
    creds = await seed_users(session, roles, branches) if with_users else []
    md = await seed_memorial_dates(session)
    await seed_synonyms(session)
    keys = await seed_catalog(session, branches, with_images)
    pages = await seed_pages(session)
    n_faq, n_news = await seed_faq_news(session, with_images)
    await seed_history(session, keys, with_images)
    await session.flush()
    indexed = await get_search_backend().rebuild(session)
    await session.commit()
    total_docs = len((await session.execute(select(Document.id))).all())
    return {
        "credentials": creds,
        "documents": total_docs,
        "indexed": indexed,
        "memorial_dates": md,
        "pages": pages,
        "faq": n_faq,
        "news": n_news,
        "keys": keys,
        "roles": roles,
        "branches": branches,
    }
