"""Санитизация rich-text из CMS (bleach) — на сервере при сохранении; на клиенте дополнительно DOMPurify."""

from __future__ import annotations

from typing import Any

import bleach

ALLOWED_TAGS = frozenset({
    "p", "br", "hr", "h2", "h3", "h4", "ul", "ol", "li", "strong", "em", "b", "i", "u", "a", "blockquote",
    "table", "thead", "tbody", "tr", "th", "td", "caption", "figure", "figcaption", "span", "small", "abbr",
})  # fmt: skip
ALLOWED_ATTRS = {
    "a": ["href", "title", "rel", "target"],
    "abbr": ["title"],
    "th": ["scope", "colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
    "span": ["lang"],
    "p": ["lang"],
}
ALLOWED_PROTOCOLS = frozenset({"http", "https", "mailto", "tel"})


def _external_rel(attrs: Any, new: bool = False) -> Any:
    href = attrs.get((None, "href"), "")
    if href.startswith(("http://", "https://")):
        attrs[(None, "target")] = "_blank"
        attrs[(None, "rel")] = "noopener noreferrer"
    return attrs


def clean_html(html: str | None) -> str | None:
    if html is None:
        return None
    cleaned = bleach.clean(
        html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, protocols=ALLOWED_PROTOCOLS, strip=True, strip_comments=True
    )
    # linkify обрабатывает и существующие <a>: внешним ссылкам добавляются target/rel
    return bleach.linkify(cleaned, callbacks=[_external_rel], skip_tags={"pre", "code"}) if cleaned else cleaned
