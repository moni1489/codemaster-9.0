"""Журнал действий, пользователи и роли, сводка, отзывы (ТЗ §6.2, §6.8)."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from app import audit
from app.admin.common import Session, get_or_404
from app.auth.deps import Principal, current_principal, deny, require
from app.auth.passwords import hash_password
from app.auth.permissions import ROLE_NAMES
from app.models import AuditLog, Branch, Document, Feedback, News, Role, SearchIndex, User, UserRole

router = APIRouter(prefix="/api/admin", tags=["admin:system"])


class AuditOut(BaseModel):
    id: int
    ts: datetime
    user_email: str | None
    action: str
    entity: str | None
    entity_id: str | None
    result: str
    ip: str | None
    details: dict[str, Any] | None


class AuditPage(BaseModel):
    items: list[AuditOut]
    total: int


@router.get("/audit", response_model=AuditPage)
async def audit_log(
    session: Session,
    result: str | None = Query(None, pattern="^(success|denied|error)$"),
    action: str | None = Query(None, max_length=64),
    user: str | None = Query(None, max_length=255),
    page: int = Query(1, ge=1, le=10_000),
    p: Principal = Depends(require("audit.read")),
) -> AuditPage:
    conds: list[Any] = []
    if result:
        conds.append(AuditLog.result == result)
    if action:
        conds.append(AuditLog.action.startswith(action, autoescape=True))
    if user:
        conds.append(AuditLog.user_email.contains(user, autoescape=True))
    total = (await session.execute(select(func.count()).select_from(AuditLog).where(*conds))).scalar_one()
    rows = (
        await session.execute(
            select(AuditLog).where(*conds).order_by(AuditLog.id.desc()).limit(50).offset((page - 1) * 50)
        )
    ).scalars()
    return AuditPage(
        items=[
            AuditOut(
                id=r.id,
                ts=r.ts,
                user_email=r.user_email,
                action=r.action,
                entity=r.entity,
                entity_id=r.entity_id,
                result=r.result,
                ip=r.ip,
                details=r.details,
            )
            for r in rows
        ],
        total=total,
    )


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    is_active: bool
    roles: list[str]
    branch: str | None
    last_login_at: datetime | None


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=255)
    role: str
    branch_id: uuid.UUID | None = None


class UserCreated(UserOut):
    temporary_password: str


async def _users(session: Any) -> list[UserOut]:
    users = (await session.execute(select(User).order_by(User.email))).scalars().all()
    branches = {b.id: b.slug for b in (await session.execute(select(Branch))).scalars()}
    return [
        UserOut(
            id=u.id,
            email=u.email,
            full_name=u.full_name,
            is_active=u.is_active,
            roles=sorted({r.role_code for r in u.roles}),
            branch=next((branches.get(r.branch_id) for r in u.roles if r.branch_id), None),
            last_login_at=u.last_login_at,
        )
        for u in users
    ]


@router.get("/users", response_model=list[UserOut])
async def list_users(session: Session, p: Principal = Depends(require("users.manage"))) -> list[UserOut]:
    return await _users(session)


@router.post("/users", response_model=UserCreated, status_code=201)
async def create_user(
    body: UserCreate, request: Request, session: Session, p: Principal = Depends(require("users.manage"))
) -> UserCreated:
    if body.role not in ROLE_NAMES:
        raise HTTPException(422, "Неизвестная роль")
    if body.role == "superadmin" and "superadmin" not in p.roles:
        await deny(
            p,
            request,
            action="users.create",
            entity="user",
            message="Назначить главного администратора может только главный администратор",
        )
    if (body.role == "branch_admin") != (body.branch_id is not None):
        raise HTTPException(422, "Филиал указывается только (и обязательно) для администратора филиала")
    if (await session.execute(select(User.id).where(func.lower(User.email) == body.email.lower()))).first():
        raise HTTPException(409, "Пользователь с таким e-mail уже существует")
    role = (await session.execute(select(Role).where(Role.code == body.role))).scalar_one()
    password = secrets.token_urlsafe(12)
    u = User(email=body.email.lower(), full_name=body.full_name, password_hash=hash_password(password))
    session.add(u)
    await session.flush()
    session.add(UserRole(user_id=u.id, role_id=role.id, role_code=role.code, branch_id=body.branch_id))
    audit.record(
        session,
        action="users.create",
        user_id=p.id,
        user_email=p.user.email,
        entity="user",
        entity_id=u.id,
        request=request,
        details={"email": u.email, "role": body.role},
    )
    await session.commit()
    session.expire_all()
    created = next(x for x in await _users(session) if x.id == u.id)
    return UserCreated(**created.model_dump(), temporary_password=password)


@router.post("/users/{user_id}/deactivate", response_model=UserOut)
async def deactivate(
    user_id: uuid.UUID, request: Request, session: Session, p: Principal = Depends(require("users.manage"))
) -> UserOut:
    u = await get_or_404(session, User, user_id, "Пользователь")
    if u.id == p.id:
        raise HTTPException(409, "Нельзя заблокировать собственную учётную запись")
    u.is_active = False
    audit.record(
        session,
        action="users.deactivate",
        user_id=p.id,
        user_email=p.user.email,
        entity="user",
        entity_id=u.id,
        request=request,
    )
    await session.commit()
    return next(x for x in await _users(session) if x.id == u.id)


class Stats(BaseModel):
    documents: int
    documents_public: int
    documents_draft: int
    review_queue: int
    news_drafts: int
    feedback_new: int


@router.get("/stats", response_model=Stats)
async def stats(session: Session, p: Principal = Depends(current_principal)) -> Stats:
    async def count(stmt: Any) -> int:
        return int((await session.execute(stmt)).scalar_one())

    docs = select(func.count()).select_from(Document)
    return Stats(
        documents=await count(docs),
        documents_public=await count(select(func.count()).select_from(SearchIndex)),
        documents_draft=await count(docs.where(Document.workflow_status == "draft")),
        review_queue=await count(docs.where(Document.workflow_status == "review"))
        + await count(select(func.count()).select_from(News).where(News.workflow_status == "review")),
        news_drafts=await count(select(func.count()).select_from(News).where(News.workflow_status == "draft")),
        feedback_new=await count(select(func.count()).select_from(Feedback).where(Feedback.status == "new")),
    )


class FeedbackOut(BaseModel):
    id: uuid.UUID
    message: str
    page: str | None
    email: str | None
    created_at: datetime


@router.get("/feedback", response_model=list[FeedbackOut])
async def feedback_list(
    session: Session, p: Principal = Depends(require("content.review", "users.manage", any_of=True))
) -> list[FeedbackOut]:
    rows = (await session.execute(select(Feedback).order_by(Feedback.created_at.desc()).limit(200))).scalars()
    return [FeedbackOut(id=f.id, message=f.message, page=f.page, email=f.email, created_at=f.created_at) for f in rows]
