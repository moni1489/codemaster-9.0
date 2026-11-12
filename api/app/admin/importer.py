"""Импорт CSV/XLSX в каталог и экспорт разрешённых данных (ТЗ §6.3, Д §3.5).

- Сопоставление колонок файла с полями каталога, предпросмотр первых строк.
- Каждая строка — отдельная вложенная транзакция (SAVEPOINT): ошибка строки не откатывает остальные.
- Дедуп по шифру; фонд/опись/дело находятся или создаются по номерам — иерархия сохраняется.
- Импортированные записи создаются черновиками (описание «Требует проверки», копия «Закрыт»).
- Экспорт — только публично видимые записи.
"""

from __future__ import annotations

import csv
import io
import json
from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from openpyxl import load_workbook
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.admin.common import Session
from app.auth.deps import Principal, require
from app.catalog.access import document_visible
from app.core.i18n import pick
from app.models import (
    ArchiveCase,
    CaseTranslation,
    Document,
    DocumentTranslation,
    Fund,
    FundTranslation,
    Inventory,
    InventoryTranslation,
)
from app.models.enums import CATEGORIES, DOC_TYPES

router = APIRouter(prefix="/api/admin/catalog", tags=["admin:import"])
MAX_ROWS = 5000
MAX_BYTES = 10 * 1024 * 1024

FIELDS: dict[str, tuple[str, bool]] = {
    "fund": ("Номер фонда", True),
    "fund_title": ("Название фонда", False),
    "inventory": ("Номер описи", True),
    "case": ("Номер дела", True),
    "case_title": ("Заголовок дела", False),
    "sheets": ("Листы", True),
    "title": ("Название документа", True),
    "category": ("Категория", True),
    "doc_type": ("Тип документа", True),
    "date_from": ("Дата с (ГГГГ-ММ-ДД или ГГГГ)", False),
    "date_to": ("Дата по", False),
    "summary": ("Краткое содержание", False),
    "author_org": ("Автор / организация", False),
    "place": ("Населённый пункт", False),
    "topic": ("Тематика", False),
    "tags": ("Ключевые слова (через ;)", False),
    "language": ("Язык документа", False),
}
SYNONYMS = {
    "fund": ["фонд", "номер фонда", "fund"],
    "fund_title": ["название фонда", "фондообразователь"],
    "inventory": ["опись", "номер описи", "inventory"],
    "case": ["дело", "номер дела", "case", "file"],
    "case_title": ["заголовок дела"],
    "sheets": ["листы", "лист", "sheets"],
    "title": ["название", "заголовок", "название документа", "title"],
    "category": ["категория", "category"],
    "doc_type": ["тип", "тип документа", "doc_type", "type"],
    "date_from": ["дата", "дата с", "date_from", "год"],
    "date_to": ["дата по", "date_to"],
    "summary": ["содержание", "аннотация", "summary"],
    "author_org": ["автор", "организация", "author"],
    "place": ["место", "населенный пункт", "населённый пункт", "place"],
    "topic": ["тема", "тематика", "topic"],
    "tags": ["ключевые слова", "теги", "tags"],
    "language": ["язык", "language"],
}


def _read(data: bytes, filename: str) -> tuple[list[str], list[list[str]]]:
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Файл больше 10 МБ")
    name = filename.lower()
    if name.endswith(".xlsx"):
        if data[:2] != b"PK":
            raise HTTPException(415, "Файл не является XLSX")
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.worksheets[0]
        rows = [["" if c is None else str(c).strip() for c in r] for r in ws.iter_rows(values_only=True)]
    elif name.endswith(".csv"):
        text = data.decode("utf-8-sig", errors="strict") if data else ""
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t") if text else csv.excel
        rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text), dialect)]
    else:
        raise HTTPException(415, "Поддерживаются только .csv и .xlsx")
    rows = [r for r in rows if any(r)]
    if not rows:
        raise HTTPException(422, "Файл пуст")
    if len(rows) - 1 > MAX_ROWS:
        raise HTTPException(413, f"Не более {MAX_ROWS} строк за один импорт")
    return rows[0], rows[1:]


def _suggest(headers: list[str]) -> dict[str, str | None]:
    low = [h.lower().strip() for h in headers]
    out: dict[str, str | None] = {}
    for field, syns in SYNONYMS.items():
        out[field] = next((headers[i] for i, h in enumerate(low) if h in syns), None)
    return out


class Preview(BaseModel):
    headers: list[str]
    rows: list[list[str]]
    total: int
    fields: dict[str, dict[str, Any]]
    suggested: dict[str, str | None]


@router.post("/import/preview", response_model=Preview)
async def preview(file: UploadFile = File(...), p: Principal = Depends(require("catalog.import"))) -> Preview:
    headers, rows = _read(await file.read(MAX_BYTES + 1), file.filename or "")
    return Preview(
        headers=headers,
        rows=rows[:20],
        total=len(rows),
        fields={k: {"label": v[0], "required": v[1]} for k, v in FIELDS.items()},
        suggested=_suggest(headers),
    )


class RowResult(BaseModel):
    row: int
    status: str  # created | duplicate | error
    cipher: str | None = None
    message: str | None = None


class ImportResult(BaseModel):
    created: int
    duplicates: int
    errors: int
    rows: list[RowResult]


def _date(v: str) -> date | None:
    v = v.strip()
    if not v:
        return None
    if len(v) == 4 and v.isdigit():
        return date(int(v), 1, 1)
    return date.fromisoformat(v[:10])


async def _get_or_create_fund(s: AsyncSession, number: str, title: str | None) -> Fund:
    f = (await s.execute(select(Fund).where(Fund.number == number))).scalar_one_or_none()
    if f:
        return f
    f = Fund(number=number, cipher=f"ГА ВКО Ф. {number}", description_status="review", workflow_status="draft")
    f.translations = [FundTranslation(lang="ru", translation_status="original", title=title or f"Фонд {number}")]
    s.add(f)
    await s.flush()
    return f


async def _get_or_create_inv(s: AsyncSession, fund: Fund, number: str) -> Inventory:
    i = (
        await s.execute(select(Inventory).where(Inventory.fund_id == fund.id, Inventory.number == number))
    ).scalar_one_or_none()
    if i:
        return i
    i = Inventory(
        fund_id=fund.id,
        number=number,
        cipher=f"{fund.cipher} Оп. {number}",
        description_status="review",
        workflow_status="draft",
    )
    i.translations = [InventoryTranslation(lang="ru", translation_status="original", title=f"Опись {number}")]
    s.add(i)
    await s.flush()
    return i


async def _get_or_create_case(s: AsyncSession, inv: Inventory, number: str, title: str | None) -> ArchiveCase:
    c = (
        await s.execute(select(ArchiveCase).where(ArchiveCase.inventory_id == inv.id, ArchiveCase.number == number))
    ).scalar_one_or_none()
    if c:
        return c
    c = ArchiveCase(
        inventory_id=inv.id,
        number=number,
        cipher=f"{inv.cipher} Д. {number}",
        description_status="review",
        workflow_status="draft",
    )
    c.translations = [CaseTranslation(lang="ru", translation_status="original", title=title or f"Дело {number}")]
    s.add(c)
    await s.flush()
    return c


@router.post("/import", response_model=ImportResult)
async def run_import(
    request: Request,
    session: Session,
    file: UploadFile = File(...),
    mapping: str = Form(..., description="JSON: {поле каталога: колонка файла}"),
    p: Principal = Depends(require("catalog.import")),
) -> ImportResult:
    headers, rows = _read(await file.read(MAX_BYTES + 1), file.filename or "")
    try:
        mp: dict[str, str | None] = json.loads(mapping)
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "Некорректное сопоставление колонок") from exc
    missing = [FIELDS[k][0] for k, (_, req) in FIELDS.items() if req and not mp.get(k)]
    if missing:
        raise HTTPException(422, f"Не сопоставлены обязательные поля: {', '.join(missing)}")
    idx = {k: headers.index(v) for k, v in mp.items() if v and v in headers}
    results: list[RowResult] = []
    for n, raw in enumerate(rows, start=2):  # нумерация как в Excel (1 — заголовок)

        def val(k: str, raw: list[str] = raw) -> str:
            i = idx.get(k)
            return raw[i].strip() if i is not None and i < len(raw) else ""

        try:
            for k, (label, req) in FIELDS.items():
                if req and not val(k):
                    raise ValueError(f"пустое обязательное поле «{label}»")
            category, doc_type = val("category"), val("doc_type")
            if category not in CATEGORIES:
                raise ValueError(f"категория «{category}» не из списка: {', '.join(CATEGORIES)}")
            if doc_type not in DOC_TYPES:
                raise ValueError(f"тип «{doc_type}» не из списка: {', '.join(DOC_TYPES)}")
            d_from, d_to = _date(val("date_from")), _date(val("date_to"))
            d_end = d_to or d_from
            if d_from and d_to and d_to < d_from:
                raise ValueError("дата окончания раньше даты начала")
            async with session.begin_nested():  # SAVEPOINT: ошибка строки не трогает остальные
                fund = await _get_or_create_fund(session, val("fund"), val("fund_title") or None)
                inv = await _get_or_create_inv(session, fund, val("inventory"))
                case = await _get_or_create_case(session, inv, val("case"), val("case_title") or None)
                cipher = f"{case.cipher} {val('sheets')}"
                if (await session.execute(select(Document.id).where(Document.cipher == cipher))).first():
                    results.append(RowResult(row=n, status="duplicate", cipher=cipher, message="шифр уже есть"))
                    continue
                doc = Document(
                    case_id=case.id,
                    inventory_id=inv.id,
                    fund_id=fund.id,
                    fund_number=fund.number,
                    inventory_number=inv.number,
                    case_number=case.number,
                    cipher=cipher,
                    sheets=val("sheets"),
                    date_from=d_from,
                    date_to=d_end,
                    year_from=d_from.year if d_from else None,
                    year_to=d_end.year if d_end else None,
                    category=category,
                    doc_type=doc_type,
                    language=val("language") or "русский",
                    branch_id=fund.branch_id,
                    is_personal_fund=fund.is_personal_fund,
                    tags=sorted({t.strip().lower() for t in val("tags").replace(",", ";").split(";") if t.strip()}),
                    description_status="review",
                    file_access="closed",
                    workflow_status="draft",
                )
                doc.translations = [
                    DocumentTranslation(
                        lang="ru",
                        translation_status="original",
                        title=val("title")[:500],
                        summary=val("summary") or None,
                        author_org=val("author_org") or None,
                        place=val("place") or None,
                        topic=val("topic") or None,
                    )
                ]
                session.add(doc)
                await session.flush()
            results.append(RowResult(row=n, status="created", cipher=cipher))
        except (ValueError, TypeError) as exc:
            results.append(RowResult(row=n, status="error", message=str(exc)[:300]))
    created = sum(r.status == "created" for r in results)
    dup = sum(r.status == "duplicate" for r in results)
    err = sum(r.status == "error" for r in results)
    audit.record(
        session,
        action="catalog.import",
        user_id=p.id,
        user_email=p.user.email,
        entity="document",
        request=request,
        details={"file": file.filename, "created": created, "duplicates": dup, "errors": err},
    )
    await session.commit()
    return ImportResult(created=created, duplicates=dup, errors=err, rows=results)


@router.get("/export.csv", include_in_schema=False)
async def export_csv(session: Session, p: Principal = Depends(require("catalog.export"))) -> Response:
    """Экспорт только публично видимых описаний (без закрытых, скрытых и черновиков)."""
    docs = (await session.execute(select(Document).where(document_visible()).order_by(Document.cipher))).scalars()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(
        ["Шифр", "Фонд", "Опись", "Дело", "Листы", "Название", "Год с", "Год по", "Категория", "Тип", "Доступ к копии"]
    )
    for d in docs:
        t = pick(d.translations, "ru", d.original_lang)
        w.writerow(
            [
                d.cipher,
                d.fund_number,
                d.inventory_number,
                d.case_number,
                d.sheets,
                t.tr.title if t else "",
                d.year_from or "",
                d.year_to or "",
                d.category,
                d.doc_type,
                d.file_access,
            ]
        )
    return Response(
        "﻿" + buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="catalog-public.csv"'},
    )
