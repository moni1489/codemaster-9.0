"""Управление электронным каталогом (ТЗ §6.3, Д §3.1, §3.5).

- Новая запись: workflow=draft, description_status=review, file_access=closed (deny by default).
- Статусы доступа меняет только обладатель права catalog.set_access (не обходится через workflow).
- Загрузка: MIME по сигнатуре, лимит размера, sha256, мастер + облегчённые WebP-копии; PDF — постранично.
"""

from __future__ import annotations

import io
import uuid
from datetime import date, datetime
from typing import Any

import pypdfium2 as pdfium
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, or_, select

from app import audit
from app.admin.common import Session, get_or_404, reload, tr_dict, upsert_translation
from app.auth.deps import Principal, require
from app.core.config import get_settings
from app.media import storage
from app.models import (
    ArchiveCase,
    CaseTranslation,
    DigitalFile,
    Document,
    DocumentTranslation,
    Fund,
    FundTranslation,
    Inventory,
    InventoryTranslation,
)
from app.models.enums import CATEGORIES, DESCRIPTION_STATUSES, DOC_TYPES, FILE_ACCESS
from app.search.postgres import get_search_backend
from app.workflow import edit_status_after, save_version

router = APIRouter(prefix="/api/admin/catalog", tags=["admin:catalog"])
READ = require("catalog.read_all", "catalog.edit", any_of=True)
MAX_PDF_PAGES = 60


# ---------------- схемы ----------------
class DocTrIn(BaseModel):
    title: str = Field(min_length=3, max_length=500)
    summary: str | None = Field(default=None, max_length=5000)
    historical_note: str | None = Field(default=None, max_length=10000)
    period_label: str | None = Field(default=None, max_length=128)
    author_org: str | None = Field(default=None, max_length=500)
    place: str | None = Field(default=None, max_length=255)
    topic: str | None = Field(default=None, max_length=255)
    access_conditions: str | None = Field(default=None, max_length=2000)


class DocFields(BaseModel):
    date_from: date | None = None
    date_to: date | None = None
    date_verified: bool = True
    category: str | None = None
    doc_type: str | None = None
    language: str | None = Field(default=None, max_length=32)
    sheets_count: int | None = Field(default=None, ge=1, le=100_000)
    storage_location: str | None = Field(default=None, max_length=255)
    tags: list[str] | None = None

    @field_validator("category")
    @classmethod
    def cat(cls, v: str | None) -> str | None:
        if v is not None and v not in CATEGORIES:
            raise ValueError(f"категория: одна из {', '.join(CATEGORIES)}")
        return v

    @field_validator("doc_type")
    @classmethod
    def dtype(cls, v: str | None) -> str | None:
        if v is not None and v not in DOC_TYPES:
            raise ValueError(f"тип документа: один из {', '.join(DOC_TYPES)}")
        return v

    @field_validator("tags")
    @classmethod
    def tags_ok(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        clean = sorted({t.strip().lower()[:64] for t in v if t.strip()})
        if len(clean) > 30:
            raise ValueError("не более 30 ключевых слов")
        return clean

    @model_validator(mode="after")
    def dates(self) -> DocFields:
        if self.date_from and self.date_to and self.date_to < self.date_from:
            raise ValueError("дата окончания раньше даты начала")
        return self


class DocCreate(DocFields):
    case_id: uuid.UUID
    sheets: str = Field(min_length=1, max_length=32, description="Листы, например «л. 3–7»")
    category: str
    doc_type: str
    translations: dict[str, DocTrIn]

    @field_validator("translations")
    @classmethod
    def ru(cls, v: dict[str, DocTrIn]) -> dict[str, DocTrIn]:
        if "ru" not in v:
            raise ValueError("обязательно название документа на русском языке")
        return v


class DocPatch(DocFields):
    translations: dict[str, DocTrIn] | None = None


class AccessPatch(BaseModel):
    description_status: str | None = None
    file_access: str | None = None
    reason: str = Field(min_length=5, max_length=1000, description="Основание изменения (в журнал)")

    @model_validator(mode="after")
    def valid(self) -> AccessPatch:
        if self.description_status and self.description_status not in DESCRIPTION_STATUSES:
            raise ValueError("недопустимый статус описания")
        if self.file_access and self.file_access not in FILE_ACCESS:
            raise ValueError("недопустимый статус доступа к файлу")
        if not self.description_status and not self.file_access:
            raise ValueError("не указано, что менять")
        return self


class FileOut(BaseModel):
    id: uuid.UUID
    kind: str
    page_no: int
    mime: str
    size: int
    sha256: str
    width: int | None
    height: int | None
    original_filename: str | None
    provenance: str | None
    rights_note: str | None
    parent_id: uuid.UUID | None
    url: str


class DocAdminOut(BaseModel):
    id: uuid.UUID
    cipher: str
    case_id: uuid.UUID
    fund_number: str
    inventory_number: str
    case_number: str
    sheets: str | None
    date_from: date | None
    date_to: date | None
    date_verified: bool
    category: str
    doc_type: str
    language: str
    sheets_count: int | None
    storage_location: str | None
    tags: list[str]
    description_status: str
    file_access: str
    workflow_status: str
    is_demo: bool
    in_public_index: bool
    updated_at: datetime
    translations: dict[str, dict[str, Any]]
    files: list[FileOut]


class DocListItem(BaseModel):
    id: uuid.UUID
    cipher: str
    title: str
    description_status: str
    file_access: str
    workflow_status: str
    is_demo: bool
    updated_at: datetime


class DocList(BaseModel):
    items: list[DocListItem]
    total: int


async def _doc_out(session: Any, d: Document) -> DocAdminOut:
    from app.models import SearchIndex

    files = (
        (
            await session.execute(
                select(DigitalFile)
                .where(DigitalFile.document_id == d.id)
                .order_by(DigitalFile.page_no, DigitalFile.kind)
            )
        )
        .scalars()
        .all()
    )
    indexed = (await session.get(SearchIndex, d.id)) is not None
    return DocAdminOut(
        id=d.id,
        cipher=d.cipher,
        case_id=d.case_id,
        fund_number=d.fund_number,
        inventory_number=d.inventory_number,
        case_number=d.case_number,
        sheets=d.sheets,
        date_from=d.date_from,
        date_to=d.date_to,
        date_verified=d.date_verified,
        category=d.category,
        doc_type=d.doc_type,
        language=d.language,
        sheets_count=d.sheets_count,
        storage_location=d.storage_location,
        tags=list(d.tags),
        description_status=d.description_status,
        file_access=d.file_access,
        workflow_status=d.workflow_status,
        is_demo=d.is_demo,
        in_public_index=indexed,
        updated_at=d.updated_at,
        translations=tr_dict(d, list(DocTrIn.model_fields)),
        files=[
            FileOut(
                id=f.id,
                kind=f.kind,
                page_no=f.page_no,
                mime=f.mime,
                size=f.size,
                sha256=f.sha256,
                width=f.width,
                height=f.height,
                original_filename=f.original_filename,
                provenance=f.provenance,
                rights_note=f.rights_note,
                parent_id=f.parent_id,
                url=f"/api/admin/catalog/media/{f.id}",
            )
            for f in files
        ],
    )


def _apply_fields(d: Document, data: dict[str, Any]) -> None:
    for k in (
        "date_from",
        "date_to",
        "date_verified",
        "category",
        "doc_type",
        "language",
        "sheets_count",
        "storage_location",
        "tags",
    ):
        if k in data and data[k] is not None:
            setattr(d, k, data[k])
    d.year_from = d.date_from.year if d.date_from else None
    d.year_to = d.date_to.year if d.date_to else d.year_from


# ---------------- документы ----------------
@router.get("/documents", response_model=DocList)
async def list_documents(
    session: Session,
    q: str | None = Query(None, max_length=200),
    workflow: str | None = None,
    description_status: str | None = None,
    file_access: str | None = None,
    page: int = Query(1, ge=1, le=1000),
    p: Principal = Depends(READ),
) -> DocList:
    conds: list[Any] = []
    if q and q.strip():
        pat = "%" + q.strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        conds.append(
            or_(
                Document.cipher.ilike(pat, escape="\\"),
                Document.id.in_(
                    select(DocumentTranslation.entity_id).where(DocumentTranslation.title.ilike(pat, escape="\\"))
                ),
            )
        )
    if workflow:
        conds.append(Document.workflow_status == workflow)
    if description_status:
        conds.append(Document.description_status == description_status)
    if file_access:
        conds.append(Document.file_access == file_access)
    total = (await session.execute(select(func.count()).select_from(Document).where(*conds))).scalar_one()
    rows = (
        (
            await session.execute(
                select(Document).where(*conds).order_by(Document.updated_at.desc()).limit(25).offset((page - 1) * 25)
            )
        )
        .scalars()
        .all()
    )
    items = []
    for d in rows:
        tr = next(
            (t for t in d.translations if t.lang == d.original_lang), d.translations[0] if d.translations else None
        )
        items.append(
            DocListItem(
                id=d.id,
                cipher=d.cipher,
                title=tr.title if tr else d.cipher,
                description_status=d.description_status,
                file_access=d.file_access,
                workflow_status=d.workflow_status,
                is_demo=d.is_demo,
                updated_at=d.updated_at,
            )
        )
    return DocList(items=items, total=total)


@router.get("/documents/{doc_id}", response_model=DocAdminOut)
async def get_document(doc_id: uuid.UUID, session: Session, p: Principal = Depends(READ)) -> DocAdminOut:
    return await _doc_out(session, await get_or_404(session, Document, doc_id, "Документ"))


@router.post("/documents", response_model=DocAdminOut, status_code=201)
async def create_document(
    body: DocCreate, request: Request, session: Session, p: Principal = Depends(require("catalog.edit"))
) -> DocAdminOut:
    case = await get_or_404(session, ArchiveCase, body.case_id, "Дело")
    inv = await get_or_404(session, Inventory, case.inventory_id, "Опись")
    fund = await get_or_404(session, Fund, inv.fund_id, "Фонд")
    cipher = f"{case.cipher} {body.sheets.strip()}"
    if (await session.execute(select(Document.id).where(Document.cipher == cipher))).first():
        raise HTTPException(409, f"Документ с шифром «{cipher}» уже существует")
    d = Document(
        case_id=case.id,
        inventory_id=inv.id,
        fund_id=fund.id,
        fund_number=fund.number,
        inventory_number=inv.number,
        case_number=case.number,
        cipher=cipher,
        sheets=body.sheets.strip(),
        category=body.category,
        doc_type=body.doc_type,
        language=body.language or "русский",
        branch_id=fund.branch_id,
        is_personal_fund=fund.is_personal_fund,
        tags=[],
        description_status="review",
        file_access="closed",
        workflow_status="draft",
    )
    _apply_fields(d, body.model_dump())
    for lang, tr in body.translations.items():
        upsert_translation(d, DocumentTranslation, lang, tr.model_dump())
    session.add(d)
    version = await save_version(session, "document", d, author_id=p.id, comment="Создание")
    audit.record(
        session,
        action="document.create",
        user_id=p.id,
        user_email=p.user.email,
        entity="document",
        entity_id=d.id,
        request=request,
        details={"cipher": cipher, "version": version},
    )
    await session.commit()
    d = await reload(session, d)
    return await _doc_out(session, d)


@router.patch("/documents/{doc_id}", response_model=DocAdminOut)
async def update_document(
    doc_id: uuid.UUID,
    body: DocPatch,
    request: Request,
    session: Session,
    p: Principal = Depends(require("catalog.edit")),
) -> DocAdminOut:
    d = await get_or_404(session, Document, doc_id, "Документ")
    data = body.model_dump(exclude_unset=True)
    _apply_fields(d, data)
    if d.date_from and d.date_to and d.date_to < d.date_from:
        raise HTTPException(422, "Дата окончания раньше даты начала")
    for lang, tr in (body.translations or {}).items():
        upsert_translation(d, DocumentTranslation, lang, tr.model_dump(), d.original_lang)
    prev = d.workflow_status
    d.workflow_status = edit_status_after(p, prev)
    version = await save_version(session, "document", d, author_id=p.id, comment="Правка")
    await session.flush()
    await get_search_backend().index_document(session, d.id)
    audit.record(
        session,
        action="document.update",
        user_id=p.id,
        user_email=p.user.email,
        entity="document",
        entity_id=d.id,
        request=request,
        details={"fields": sorted(data), "version": version, "status": f"{prev}->{d.workflow_status}"},
    )
    await session.commit()
    d = await reload(session, d)
    return await _doc_out(session, d)


@router.patch("/documents/{doc_id}/access", response_model=DocAdminOut)
async def update_access(
    doc_id: uuid.UUID,
    body: AccessPatch,
    request: Request,
    session: Session,
    p: Principal = Depends(require("catalog.set_access")),
) -> DocAdminOut:
    d = await get_or_404(session, Document, doc_id, "Документ")
    before = {"description_status": d.description_status, "file_access": d.file_access}
    if body.description_status:
        d.description_status = body.description_status
    if body.file_access:
        d.file_access = body.file_access
    await save_version(session, "document", d, author_id=p.id, comment=f"Доступ: {body.reason}")
    await session.flush()
    await get_search_backend().index_document(session, d.id)
    audit.record(
        session,
        action="document.access",
        user_id=p.id,
        user_email=p.user.email,
        entity="document",
        entity_id=d.id,
        request=request,
        details={
            "before": before,
            "after": {"description_status": d.description_status, "file_access": d.file_access},
            "reason": body.reason,
        },
    )
    await session.commit()
    d = await reload(session, d)
    return await _doc_out(session, d)


@router.delete("/documents/{doc_id}", status_code=204, response_model=None)
async def delete_document(
    doc_id: uuid.UUID,
    request: Request,
    session: Session,
    confirm: str = Query(..., description="Шифр документа"),
    p: Principal = Depends(require("catalog.delete")),
) -> None:
    d = await get_or_404(session, Document, doc_id, "Документ")
    if confirm.strip() != d.cipher:
        raise HTTPException(409, "Для удаления подтвердите шифр документа")
    files = (await session.execute(select(DigitalFile).where(DigitalFile.document_id == d.id))).scalars().all()
    await save_version(session, "document", d, author_id=p.id, comment="Удаление (последний снимок)")
    audit.record(
        session,
        action="document.delete",
        user_id=p.id,
        user_email=p.user.email,
        entity="document",
        entity_id=d.id,
        request=request,
        details={"cipher": d.cipher, "files": len(files)},
    )
    keys = [f.storage_key for f in files]
    await session.delete(d)
    await session.commit()
    for key in keys:
        storage.resolve(key).unlink(missing_ok=True)


# ---------------- файлы ----------------
def _pdf_pages(data: bytes) -> list[bytes]:
    pdf = pdfium.PdfDocument(data)
    try:
        if len(pdf) > MAX_PDF_PAGES:
            raise HTTPException(413, f"PDF больше {MAX_PDF_PAGES} страниц — загрузите частями")
        out = []
        for i in range(len(pdf)):
            img = pdf[i].render(scale=2).to_pil().convert("RGB")
            buf = io.BytesIO()
            img.save(buf, "PNG")
            out.append(buf.getvalue())
        return out
    finally:
        pdf.close()


@router.post("/documents/{doc_id}/files", response_model=DocAdminOut, status_code=201)
async def upload_files(
    doc_id: uuid.UUID,
    request: Request,
    session: Session,
    files: list[UploadFile] = File(...),
    provenance: str = Form(..., min_length=3, max_length=1000, description="Происхождение файла"),
    rights_note: str = Form(..., min_length=2, max_length=500, description="Права на публикацию"),
    p: Principal = Depends(require("files.upload")),
) -> DocAdminOut:
    d = await get_or_404(session, Document, doc_id, "Документ")
    limit = get_settings().max_upload_mb * 1024 * 1024
    next_page = (
        int(
            (
                await session.execute(
                    select(func.coalesce(func.max(DigitalFile.page_no), 0)).where(DigitalFile.document_id == d.id)
                )
            ).scalar_one()
        )
        + 1
    )
    stored: list[str] = []
    for up in files:
        data = await up.read(limit + 1)
        if len(data) > limit:
            raise HTTPException(413, f"Файл «{up.filename}» больше {get_settings().max_upload_mb} МБ")
        try:
            master = storage.store_master(data, limit)
        except storage.UnsupportedFile as exc:
            raise HTTPException(415, f"«{up.filename}»: {exc}") from exc
        if (
            await session.execute(
                select(DigitalFile.id).where(
                    DigitalFile.document_id == d.id, DigitalFile.sha256 == master.sha256, DigitalFile.kind == "master"
                )
            )
        ).first():
            storage.resolve(master.storage_key).unlink(missing_ok=True)
            raise HTTPException(409, f"«{up.filename}» уже загружен (совпадает sha256)")
        m = DigitalFile(
            document_id=d.id,
            kind="master",
            page_no=next_page,
            storage_key=master.storage_key,
            mime=master.mime,
            size=master.size,
            sha256=master.sha256,
            width=master.width,
            height=master.height,
            original_filename=(up.filename or "")[:255],
            uploaded_by=p.id,
            provenance=provenance,
            rights_note=rights_note,
        )
        session.add(m)
        await session.flush()
        stored.append(master.storage_key)
        pages: list[bytes] = []
        if master.mime in storage.IMAGE_MIMES:
            pages = [data]
        elif master.mime == "application/pdf":
            pages = _pdf_pages(data)
        for offset, page_bytes in enumerate(pages):
            view, thumb = storage.store_derivatives(page_bytes)
            for st, kind in ((view, "view"), (thumb, "thumb")):
                session.add(
                    DigitalFile(
                        document_id=d.id,
                        parent_id=m.id,
                        kind=kind,
                        page_no=next_page + offset,
                        storage_key=st.storage_key,
                        mime=st.mime,
                        size=st.size,
                        sha256=st.sha256,
                        width=st.width,
                        height=st.height,
                        uploaded_by=p.id,
                        provenance=provenance,
                        rights_note=rights_note,
                    )
                )
        next_page += max(1, len(pages))
        audit.record(
            session,
            action="file.upload",
            user_id=p.id,
            user_email=p.user.email,
            entity="document",
            entity_id=d.id,
            request=request,
            details={
                "file": up.filename,
                "mime": master.mime,
                "size": master.size,
                "sha256": master.sha256,
                "pages": len(pages),
            },
        )
    await session.commit()
    d = await reload(session, d)
    return await _doc_out(session, d)


@router.get("/media/{file_id}", response_class=FileResponse, include_in_schema=False)
async def staff_media(file_id: uuid.UUID, session: Session, p: Principal = Depends(READ)) -> FileResponse:
    f = await get_or_404(session, DigitalFile, file_id, "Файл")
    path = storage.resolve(f.storage_key)
    if not path.is_file():
        raise HTTPException(404, "Файл отсутствует в хранилище")
    return FileResponse(
        path, media_type=f.mime, headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    )


# ---------------- иерархия ----------------
class TreeCase(BaseModel):
    id: uuid.UUID
    number: str
    cipher: str
    title: str


class TreeInventory(BaseModel):
    id: uuid.UUID
    number: str
    title: str
    cases: list[TreeCase]


class TreeFund(BaseModel):
    id: uuid.UUID
    number: str
    title: str
    inventories: list[TreeInventory]


def _ru(obj: Any) -> str:
    tr = next((t for t in obj.translations if t.lang == "ru"), None)
    return str(tr.title) if tr else str(obj.cipher)


@router.get("/tree", response_model=list[TreeFund])
async def tree(session: Session, p: Principal = Depends(READ)) -> list[TreeFund]:
    funds = (await session.execute(select(Fund).order_by(Fund.number))).scalars().all()
    invs = (await session.execute(select(Inventory).order_by(Inventory.number))).scalars().all()
    cases = (await session.execute(select(ArchiveCase).order_by(ArchiveCase.number))).scalars().all()
    return [
        TreeFund(
            id=f.id,
            number=f.number,
            title=_ru(f),
            inventories=[
                TreeInventory(
                    id=i.id,
                    number=i.number,
                    title=_ru(i),
                    cases=[
                        TreeCase(id=c.id, number=c.number, cipher=c.cipher, title=_ru(c))
                        for c in cases
                        if c.inventory_id == i.id
                    ],
                )
                for i in invs
                if i.fund_id == f.id
            ],
        )
        for f in funds
    ]


class UnitIn(BaseModel):
    parent_id: uuid.UUID | None = None  # для описи — фонд, для дела — опись
    number: str = Field(min_length=1, max_length=32, pattern=r"^[0-9A-Za-zА-Яа-яЁё\-/.]+$")
    title_ru: str = Field(min_length=3, max_length=500)
    year_from: int | None = Field(default=None, ge=1500, le=2100)
    year_to: int | None = Field(default=None, ge=1500, le=2100)
    is_personal_fund: bool = False
    sheets_count: int | None = Field(default=None, ge=1)


@router.post("/{level}", response_model=TreeCase, status_code=201)
async def create_unit(
    level: str, body: UnitIn, request: Request, session: Session, p: Principal = Depends(require("catalog.edit"))
) -> TreeCase:
    common = {
        "number": body.number,
        "year_from": body.year_from,
        "year_to": body.year_to,
        "description_status": "review",
        "workflow_status": "draft",
    }
    obj: Fund | Inventory | ArchiveCase
    if level == "funds":
        cipher = f"ГА ВКО Ф. {body.number}"
        obj = Fund(cipher=cipher, is_personal_fund=body.is_personal_fund, **common)
        obj.translations = [FundTranslation(lang="ru", translation_status="original", title=body.title_ru)]
    elif level == "inventories":
        fund = await get_or_404(session, Fund, body.parent_id or uuid.UUID(int=0), "Фонд")
        cipher = f"{fund.cipher} Оп. {body.number}"
        obj = Inventory(fund_id=fund.id, cipher=cipher, **common)
        obj.translations = [InventoryTranslation(lang="ru", translation_status="original", title=body.title_ru)]
    elif level == "cases":
        inv = await get_or_404(session, Inventory, body.parent_id or uuid.UUID(int=0), "Опись")
        cipher = f"{inv.cipher} Д. {body.number}"
        obj = ArchiveCase(inventory_id=inv.id, cipher=cipher, sheets_count=body.sheets_count, **common)
        obj.translations = [CaseTranslation(lang="ru", translation_status="original", title=body.title_ru)]
    else:
        raise HTTPException(404, "Неизвестный уровень")
    if (await session.execute(select(type(obj).id).where(type(obj).cipher == cipher))).first():
        raise HTTPException(409, f"Шифр «{cipher}» уже существует")
    session.add(obj)
    await session.flush()
    audit.record(
        session,
        action=f"{level}.create",
        user_id=p.id,
        user_email=p.user.email,
        entity=level,
        entity_id=obj.id,
        request=request,
        details={"cipher": cipher},
    )
    await session.commit()
    return TreeCase(id=obj.id, number=obj.number, cipher=cipher, title=body.title_ru)
