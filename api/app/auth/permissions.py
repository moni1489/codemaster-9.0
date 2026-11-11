"""Матрица прав (ТЗ §6.1). Хранится в БД (permissions/role_permissions) и настраивается из админки;
здесь — значения по умолчанию для сида. Проверка выполняется на сервере для каждой операции и объекта."""

from __future__ import annotations

from typing import Final

PERMISSIONS: Final[dict[str, str]] = {
    "catalog.read_all": "Просмотр всех записей каталога, включая скрытые и закрытые",
    "catalog.edit": "Создание и редактирование записей каталога",
    "catalog.delete": "Удаление записей каталога",
    "catalog.set_access": "Изменение статусов публикации описания и доступа к файлу",
    "catalog.import": "Импорт CSV/XLSX",
    "catalog.export": "Экспорт разрешённых данных",
    "files.upload": "Загрузка цифровых копий",
    "content.edit": "Создание и редактирование новостей, страниц, FAQ, выставок, коллекций",
    "content.submit": "Передача материала на проверку",
    "content.review": "Согласование: одобрить / вернуть на доработку",
    "content.publish": "Публикация и снятие с публикации",
    "content.delete": "Удаление материалов",
    "branches.edit_any": "Редактирование любого филиала",
    "branches.edit_own": "Редактирование своего филиала (branch_admin)",
    "users.manage": "Управление пользователями и ролями",
    "settings.manage": "Системные настройки и интеграции",
    "audit.read": "Просмотр журнала действий",
    "analytics.read": "Просмотр аналитики",
    "ocr.use": "OCR и автоматическое извлечение метаданных",
}

ROLE_PERMISSIONS: Final[dict[str, set[str]]] = {
    "superadmin": set(PERMISSIONS),
    "site_admin": {
        "content.edit", "content.submit", "content.review", "content.publish", "content.delete",
        "branches.edit_any", "users.manage", "audit.read", "analytics.read", "catalog.read_all",
    },
    "editor": {"content.edit", "content.submit"},
    "archivist": {
        "catalog.read_all", "catalog.edit", "catalog.import", "catalog.export", "files.upload",
        "content.submit", "ocr.use",
    },
    "branch_admin": {"branches.edit_own"},
    "moderator": {"content.review", "content.publish", "catalog.read_all", "catalog.set_access"},
    "analyst": {"analytics.read"},
}  # fmt: skip

ROLE_NAMES: Final[dict[str, str]] = {
    "superadmin": "Главный администратор",
    "site_admin": "Администратор сайта",
    "editor": "Редактор",
    "archivist": "Сотрудник архива",
    "branch_admin": "Администратор филиала",
    "moderator": "Модератор",
    "analyst": "Аналитик",
}
