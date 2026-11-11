"""Перечни допустимых значений. В БД — CHECK-ограничения; всё, что вне перечня, трактуется как закрытое."""

from __future__ import annotations

from typing import Final

LANGS: Final = ("kk", "ru", "en")
DEFAULT_LANG: Final = "ru"

DESCRIPTION_STATUSES: Final = ("public", "hidden", "review")
FILE_ACCESS: Final = ("open", "restricted", "closed")
WORKFLOW_STATUSES: Final = ("draft", "review", "needs_rework", "approved", "published", "archived")
TRANSLATION_STATUSES: Final = ("original", "verified", "machine", "missing")
BRANCH_TYPES: Final = ("main", "branch")
DIGITAL_FILE_KINDS: Final = ("master", "view", "thumb")

# Категории каталога по ТЗ §5.3
CATEGORIES: Final = ("historical", "photo", "map", "written", "organization", "personal", "audiovisual")
DOC_TYPES: Final = (
    "photo", "order", "protocol", "decision", "report", "map", "plan", "newspaper",
    "letter", "certificate", "biography", "poster", "audio", "video", "memoir",
)  # fmt: skip

ROLES: Final = ("superadmin", "site_admin", "editor", "archivist", "branch_admin", "moderator", "analyst")


def check_in(column: str, values: tuple[str, ...]) -> str:
    """Текст CHECK-ограничения `column IN (...)` из констант (не из пользовательского ввода)."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{column} IN ({quoted})"
