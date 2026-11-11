"""Все ORM-модели (импорт нужен для Alembic autogenerate)."""

from app.models.auth import Permission, Role, RolePermission, User, UserRole
from app.models.base import Base
from app.models.branches import Branch, BranchTranslation
from app.models.catalog import (
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
from app.models.cms import (
    Faq,
    FaqGroup,
    FaqGroupTranslation,
    FaqTranslation,
    Feedback,
    MemorialDate,
    MemorialDateTranslation,
    News,
    NewsTranslation,
    Page,
    PageTranslation,
)
from app.models.history import (
    Collection,
    CollectionItem,
    CollectionTranslation,
    Event,
    EventTranslation,
    Exhibit,
    Exhibition,
    ExhibitionTranslation,
    ExhibitTranslation,
    Person,
    PersonTranslation,
)
from app.models.system import AuditLog, ContentVersion, SearchIndex, SearchLog, Synonym

__all__ = [
    "ArchiveCase", "AuditLog", "Base", "Branch", "BranchTranslation", "CaseTranslation", "Collection",
    "CollectionItem", "CollectionTranslation", "ContentVersion", "DigitalFile", "Document",
    "DocumentTranslation", "Event", "EventTranslation", "Exhibit", "ExhibitTranslation", "Exhibition",
    "ExhibitionTranslation", "Faq", "FaqGroup", "FaqGroupTranslation", "FaqTranslation", "Feedback",
    "Fund", "FundTranslation", "Inventory", "InventoryTranslation", "MemorialDate",
    "MemorialDateTranslation", "News", "NewsTranslation", "Page", "PageTranslation", "Permission",
    "Person", "PersonTranslation", "Role", "RolePermission", "SearchIndex", "SearchLog", "Synonym",
    "User", "UserRole",
]  # fmt: skip
