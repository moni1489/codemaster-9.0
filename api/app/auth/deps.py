"""Проверка прав на сервере для каждой операции (Д §3.5). Скрытие пунктов меню на клиенте — не защита."""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.auth import session as sess
from app.core.config import get_settings
from app.core.db import get_session
from app.models import Permission, RolePermission, User, UserRole

UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass
class Principal:
    user: User
    roles: list[str]
    permissions: set[str]
    branch_ids: set[uuid.UUID] = field(default_factory=set)

    @property
    def id(self) -> uuid.UUID:
        return self.user.id

    def has(self, perm: str) -> bool:
        return perm in self.permissions


async def load_permissions(session: AsyncSession, user: User) -> tuple[list[str], set[str], set[uuid.UUID]]:
    roles = (await session.execute(select(UserRole).where(UserRole.user_id == user.id))).scalars().all()
    role_ids = [r.role_id for r in roles]
    perms = (
        await session.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id.in_(role_ids))
        )
    ).scalars()
    branch_ids = {r.branch_id for r in roles if r.branch_id is not None}
    return sorted({r.role_code for r in roles}), set(perms), branch_ids


async def current_principal(
    request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> Principal:
    claims = sess.decode(request.cookies.get(sess.SESSION_COOKIE))
    if claims is None:
        raise HTTPException(401, "Требуется вход")
    if request.method in UNSAFE and not sess.csrf_ok(claims, request.headers.get(sess.CSRF_HEADER)):
        await audit.record_now(
            action="csrf.reject", result="denied", request=request, details={"path": request.url.path}
        )
        raise HTTPException(403, "CSRF-проверка не пройдена")
    try:
        user_id = uuid.UUID(claims.user_id)
    except ValueError as exc:
        raise HTTPException(401, "Требуется вход") from exc
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise HTTPException(401, "Требуется вход")
    roles, perms, branches = await load_permissions(session, user)
    # скользящий срок: активность продлевает сессию (не чаще раза в минуту)
    idle = get_settings().session_idle_minutes * 60
    if claims.exp - time.time() < idle - 60:
        sess.issue(response, str(user.id), csrf=claims.csrf, auth_time=claims.auth_time)
    return Principal(user=user, roles=roles, permissions=perms, branch_ids=branches)


def require(*perms: str, any_of: bool = False) -> Callable[..., Awaitable[Principal]]:
    """Зависимость: у пользователя есть все (или хотя бы одно при any_of) из прав."""

    async def dependency(request: Request, principal: Principal = Depends(current_principal)) -> Principal:
        ok = any(principal.has(p) for p in perms) if any_of else all(principal.has(p) for p in perms)
        if not ok:
            await deny(principal, request, action=f"perm:{'|'.join(perms)}")
        return principal

    return dependency


async def deny(
    principal: Principal,
    request: Request,
    *,
    action: str,
    entity: str | None = None,
    entity_id: str | uuid.UUID | None = None,
    message: str = "Недостаточно прав для этой операции",
) -> None:
    """Записать отказ в журнал (отдельной транзакцией) и вернуть 403."""
    await audit.record_now(
        action=action,
        result="denied",
        user_id=principal.id,
        user_email=principal.user.email,
        entity=entity,
        entity_id=entity_id,
        request=request,
    )
    raise HTTPException(403, message)
