"""Журнал действий админки (ТЗ §6.8, Д §3.5): кто, что, над каким объектом, результат, IP.

Пароли, токены и содержимое документов не записываются. Отказ в доступе (`denied`) фиксируется
в отдельной транзакции, чтобы запись сохранилась, даже если основной запрос откатывается.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import sessionmaker
from app.core.logging import log
from app.models import AuditLog

_SECRET_KEYS = {"password", "password_hash", "token", "csrf", "secret"}


def _safe(details: dict[str, Any] | None) -> dict[str, Any] | None:
    if not details:
        return None
    return {k: ("***" if k.lower() in _SECRET_KEYS else v) for k, v in details.items()}


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host if request.client else None


def record(
    session: AsyncSession,
    *,
    action: str,
    result: str = "success",
    user_id: uuid.UUID | None = None,
    user_email: str | None = None,
    entity: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    request: Request | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Добавить запись в текущую транзакцию (сохранится вместе с изменением)."""
    session.add(
        AuditLog(
            user_id=user_id,
            user_email=user_email,
            action=action,
            entity=entity,
            entity_id=str(entity_id) if entity_id else None,
            result=result,
            ip=client_ip(request),
            details=_safe(details),
        )
    )


async def record_now(**kwargs: Any) -> None:
    """Записать немедленно в отдельной транзакции (для отказов и неудачных входов)."""
    try:
        async with sessionmaker()() as s:
            record(s, **kwargs)
            await s.commit()
    except Exception as exc:  # журнал не должен ронять запрос
        log.error("audit_write_failed", error=type(exc).__name__)
