"""Сборка seed/memorial_dates.json из DOCX-календарей заказчика (2022–2026, каз/рус).

Запуск (только stdlib):  python seed/tools/build_memorial_dates.py
Источник: docs/source/Календарь памятных дат/календарь <год> год каз рус.docx

В каждом файле две таблицы «дата | событие»: казахская и русская (порядок разный по годам).
Язык секции определяется по заголовку. Пары kk↔ru сопоставляются по (месяц, день) в порядке
следования; непарные записи получают translation_status='missing' для второго языка.
"""

from __future__ import annotations

import json
import re
import sys
import zipfile
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs" / "source" / "Календарь памятных дат"
OUT = ROOT / "seed" / "memorial_dates.json"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

MONTHS = {
    # ru (именительный и родительный)
    "январ": 1, "феврал": 2, "март": 3, "апрел": 4, "ма": 5, "июн": 6,
    "июл": 7, "август": 8, "сентябр": 9, "октябр": 10, "ноябр": 11, "декабр": 12,
    # kk
    "қаңтар": 1, "ақпан": 2, "наурыз": 3, "сәуір": 4, "мамыр": 5, "маусым": 6,
    "шілде": 7, "тамыз": 8, "қыркүйек": 9, "қазан": 10, "қараша": 11, "желтоқсан": 12,
}
# порядок проверки: длинные основы раньше коротких ("май"/"мая" → "ма" проверяем последним)
MONTH_KEYS = sorted(MONTHS, key=len, reverse=True)


def rows(path: Path) -> list[tuple[str, ...]]:
    """Плоский список: заголовки — кортеж из 1 элемента, строки таблиц — из ≥2."""
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    body = root.find(W + "body")
    assert body is not None

    def text(el: ET.Element) -> str:
        return " ".join("".join(t.text or "" for t in el.iter(W + "t")).split())

    out: list[tuple[str, ...]] = []
    for el in body:
        if el.tag == W + "p":
            out.append((text(el),))
        elif el.tag == W + "tbl":
            for tr in el.iter(W + "tr"):
                # абзацы внутри ячейки — отдельные события/строки: соединяем через «; », а не вплотную
                out.append(
                    tuple(
                        "; ".join(p for p in (text(par) for par in tc.iter(W + "p")) if p) for tc in tr.findall(W + "tc")
                    )
                )
    return out


def detect_lang(line: str) -> str | None:
    low = line.lower()
    if "календар" in low:
        return "ru"
    if "жылға арналған" in low or "күнтізбе" in low:
        return "kk"
    return None


def parse_date(label: str) -> tuple[int | None, int | None]:
    low = label.lower().strip()
    m = re.match(r"^(\d{1,2})\s+([^\s\d]+)", low)
    day = int(m.group(1)) if m else None
    word = m.group(2) if m else low.split(" ")[0] if low else ""
    for key in MONTH_KEYS:
        if word.startswith(key):
            if key == "ма" and not (word in {"май", "мая"}):
                continue
            return MONTHS[key], day
    return None, None


def build() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for path in sorted(SRC.glob("календарь * год каз рус.docx")):
        year = int(re.search(r"(\d{4})", path.name).group(1))  # type: ignore[union-attr]
        lang: str | None = None
        entries: dict[str, list[dict[str, object]]] = {"ru": [], "kk": []}
        for row in rows(path):
            for cell in row:
                found = detect_lang(cell)
                if found:
                    lang = found
            if len(row) < 2 or lang is None:
                continue
            date_label, title = row[0], " ".join(c for c in row[1:] if c)
            if not title or not date_label or date_label.lower().startswith(("оқиға", "дата")):
                continue
            if detect_lang(title):
                continue
            month, day = parse_date(date_label)
            entries[lang].append({"date_label": date_label, "title": title, "month": month, "day": day})

        kk_by_key: dict[tuple[object, object], list[dict[str, object]]] = defaultdict(list)
        for e in entries["kk"]:
            kk_by_key[(e["month"], e["day"])].append(e)
        used: set[int] = set()
        for e in entries["ru"]:
            pool = kk_by_key.get((e["month"], e["day"]), [])
            kk = next((k for k in pool if id(k) not in used and e["month"] is not None), None)
            if kk is not None:
                used.add(id(kk))
            result.append(_item(year, e, kk))
        for e in entries["kk"]:
            if id(e) not in used:
                result.append(_item(year, None, e))
    for i, item in enumerate(result, 1):
        item["id"] = f"md-{item['year']}-{i:04d}"
    return result


def _item(year: int, ru: dict[str, object] | None, kk: dict[str, object] | None) -> dict[str, object]:
    base = ru or kk
    assert base is not None
    return {
        "year": year,
        "month": base["month"],
        "day": base["day"],
        "date_label": {"ru": ru["date_label"] if ru else None, "kk": kk["date_label"] if kk else None},
        "title": {"ru": ru["title"] if ru else None, "kk": kk["title"] if kk else None},
        "translation_status": {
            "ru": "original" if ru else "missing",
            "kk": "original" if kk else "missing",
            "en": "missing",
        },
        "source": f"docs/source/Календарь памятных дат/календарь {year} год каз рус.docx",
    }


if __name__ == "__main__":
    data = build()
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    paired = sum(1 for d in data if d["title"]["ru"] and d["title"]["kk"])  # type: ignore[index]
    print(f"{OUT.relative_to(ROOT)}: {len(data)} записей, пар ru+kk: {paired}", file=sys.stderr)
