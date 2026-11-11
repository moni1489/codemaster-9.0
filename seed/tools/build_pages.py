"""Генерация HTML-тел справочных страниц из DOCX заказчика (только stdlib).

Запуск: python seed/tools/build_pages.py
Результат: seed/content/pages/<slug>.<lang>.html (коммитятся; дальше правятся через админку).
"""

from __future__ import annotations

import html
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs" / "source"
OUT = ROOT / "seed" / "content" / "pages"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

JOBS = [
    ("about-history", "ru", SRC / "История архива.docx", 1),  # пропустить заголовок «История архива»
    ("compliance", "ru", SRC / "Комплаенс служба" / "Информация о работе комплаенс службы.docx", 0),
    ("compliance", "kk", SRC / "Комплаенс служба" / "Информация каз.docx", 0),
]


def paragraphs(path: Path) -> list[str]:
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml"))
    out = []
    for p in root.iter(W + "p"):
        text = " ".join("".join(t.text or "" for t in p.iter(W + "t")).split())
        if text:
            out.append(text)
    return out


def to_html(paras: list[str]) -> str:
    lines = []
    for p in paras:
        if p.startswith(("- ", "-")) and len(p) > 2:
            lines.append(f"<ul><li>{html.escape(p.lstrip('- ').strip())}</li></ul>")
        else:
            lines.append(f"<p>{html.escape(p)}</p>")
    return "\n".join(lines).replace("</ul>\n<ul>", "\n") + "\n"


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for slug, lang, path, skip in JOBS:
        target = OUT / f"{slug}.{lang}.html"
        target.write_text(to_html(paragraphs(path)[skip:]), encoding="utf-8")
        print(target.relative_to(ROOT))
