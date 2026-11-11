"""Вход/выход сотрудников. Ограничение попыток: 5/мин с IP и 10/час на учётную запись."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import audit
from app.auth import session as sess
from app.auth.deps import Principal, current_principal, load_permissions
from app.auth.passwords import hash_password, verify_password
from app.core.db import get_session
from app.core.ratelimit import limiter, rate_limit
from app.models import Branch, User

router = APIRouter(prefix="/api/auth", tags=["auth"])
# хеш-«пустышка»: проверка выполняется и для несуществующего e-mail (одинаковое время ответа)
_DUMMY_HASH = hash_password("dummy-password-for-timing")


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class BranchShort(BaseModel):
    id: uuid.UUID
    slug: str


class MeOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    roles: list[str]
    permissions: list[str]
    branches: list[BranchShort]
    idle_minutes: int


async def me_out(session: AsyncSession, p: Principal) -> MeOut:
    from app.core.config import get_settings

    branches = (await session.execute(select(Branch).where(Branch.id.in_(p.branch_ids)))).scalars().all()
    return MeOut(
        id=p.id,
        email=p.user.email,
        full_name=p.user.full_name,
        roles=p.roles,
        permissions=sorted(p.permissions),
        branches=[BranchShort(id=b.id, slug=b.slug) for b in branches],
        idle_minutes=get_settings().session_idle_minutes,
    )


@router.post("/login", response_model=MeOut, dependencies=[Depends(rate_limit("5/minute", "login"))])
async def login(
    body: LoginIn, request: Request, response: Response, session: AsyncSession = Depends(get_session)
) -> MeOut:
    email = body.email.strip().lower()
    if not limiter.hit("10/hour", "login-account", email):
        await audit.record_now(
            action="auth.login",
            result="denied",
            user_email=email,
            request=request,
            details={"reason": "account_rate_limit"},
        )
        raise HTTPException(429, "Слишком много попыток входа. Повторите позже.")
    user = (await session.execute(select(User).where(func.lower(User.email) == email))).scalar_one_or_none()
    valid = verify_password(body.password, user.password_hash if user else _DUMMY_HASH)
    if not user or not valid or not user.is_active:
        if user:
            user.failed_logins += 1
            await session.commit()
        await audit.record_now(
            action="auth.login", result="denied", user_id=user.id if user else None, user_email=email, request=request
        )
        raise HTTPException(401, "Неверный e-mail или пароль")
    user.failed_logins = 0
    user.last_login_at = datetime.now(UTC)
    audit.record(session, action="auth.login", user_id=user.id, user_email=user.email, request=request)
    await session.commit()
    sess.issue(response, str(user.id))
    roles, perms, branches = await load_permissions(session, user)
    return await me_out(session, Principal(user=user, roles=roles, permissions=perms, branch_ids=branches))


@router.post("/logout", status_code=204, response_model=None)
async def logout(
    request: Request,
    response: Response,
    p: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> Response:
    audit.record(session, action="auth.logout", user_id=p.id, user_email=p.user.email, request=request)
    await session.commit()
    out = Response(status_code=204)
    sess.clear(out)
    return out


@router.get("/me", response_model=MeOut)
async def me(p: Principal = Depends(current_principal), session: AsyncSession = Depends(get_session)) -> MeOut:
    return await me_out(session, p)
