"""Импорт CSV/XLSX (Д §3.5): сопоставление, предпросмотр, протокол, дедуп, построчные транзакции; экспорт."""

import io
import json
from typing import Any

from openpyxl import Workbook

CSV = (
    "Фонд;Опись;Дело;Листы;Название;Категория;Тип;Дата\n"
    "Р-777;1;1;л. 1;Импортированный приказ;organization;order;1959-03-01\n"
    "Р-777;1;1;л. 1;Дубль по шифру;organization;order;1959\n"
    "Р-777;1;2;л. 5;Плохая категория;nonsense;order;1960\n"
    "Р-777;1;2;л. 6;;organization;order;1960\n"
    "Р-777;2;1;л. 2;Вторая опись;photo;photo;1961\n"
)


async def test_import_csv_protocol(login: Any) -> None:
    arch = await login("archivist")
    files = {"file": ("cat.csv", CSV.encode("utf-8"), "text/csv")}
    prev = (await arch.post("/api/admin/catalog/import/preview", files=files)).json()
    assert prev["total"] == 5 and prev["suggested"]["fund"] == "Фонд" and prev["suggested"]["title"] == "Название"
    mapping = {k: v for k, v in prev["suggested"].items() if v}
    r = await arch.post("/api/admin/catalog/import", files=files, data={"mapping": json.dumps(mapping)})
    assert r.status_code == 200, r.text
    res = r.json()
    assert (res["created"], res["duplicates"], res["errors"]) == (2, 1, 2)
    statuses = {row["row"]: row["status"] for row in res["rows"]}
    assert statuses == {2: "created", 3: "duplicate", 4: "error", 5: "error", 6: "created"}
    assert "категория" in res["rows"][2]["message"]
    # иерархия создана, записи — черновики и закрыты по умолчанию
    docs = (await arch.get("/api/admin/catalog/documents", params={"q": "Р-777"})).json()
    assert docs["total"] == 2 and all(
        d["workflow_status"] == "draft" and d["file_access"] == "closed" for d in docs["items"]
    )
    # повторный импорт: всё дубли
    again = (await arch.post("/api/admin/catalog/import", files=files, data={"mapping": json.dumps(mapping)})).json()
    assert again["created"] == 0 and again["duplicates"] == 3


async def test_import_xlsx_and_required_mapping(login: Any) -> None:
    arch = await login("archivist")
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["fund", "inventory", "case", "sheets", "title", "category", "doc_type"])
    ws.append(["Р-778", "1", "3", "л. 9", "Из Excel", "map", "map"])
    buf = io.BytesIO()
    wb.save(buf)
    files = {"file": ("cat.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    bad = await arch.post("/api/admin/catalog/import", files=files, data={"mapping": json.dumps({"fund": "fund"})})
    assert bad.status_code == 422
    prev = (await arch.post("/api/admin/catalog/import/preview", files=files)).json()
    mapping = {k: v for k, v in prev["suggested"].items() if v}
    assert (await arch.post("/api/admin/catalog/import", files=files, data={"mapping": json.dumps(mapping)})).json()[
        "created"
    ] == 1
    assert (
        await arch.post(
            "/api/admin/catalog/import/preview", files={"file": ("x.exe", b"MZ", "application/octet-stream")}
        )
    ).status_code == 415


async def test_export_only_public(login: Any, seeded: dict) -> None:  # type: ignore[type-arg]
    arch = await login("archivist")
    text = (await arch.get("/api/admin/catalog/export.csv")).text
    assert "Набережная Иртыша" in text and "Личные карточки" not in text and "Р-777" not in text
    editor = await login("editor")
    assert (await editor.get("/api/admin/catalog/export.csv")).status_code == 403
