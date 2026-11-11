"""Управление филиалами (ТЗ §6.4). branch_admin правит только СВОЙ филиал и только контакты (Д §3.5)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select

from app import audit
from app.admin.common import Session, get_or_404, reload, tr_dict, upsert_translation
from app.auth.deps import Principal, deny, require
from app.models import Branch, BranchTranslation

router = APIRouter(prefix="/api/admin/branches", tags=["admin:branches"])
STAFF = require("branches.edit_any", "branches.edit_own", any_of=True)
# поля, которые может менять администратор своего филиала
OWN_FIELDS = {"phone", "email", "director", "translations"}


class BranchTrIn(BaseModel):
    address: str | None = Field(default=None, max_length=500)
    hours: str | None = Field(default=None, max_length=500)
    description: str | None = Field(default=None, max_length=4000)


class BranchPatch(BaseModel):
    phone: str | None = Field(default=None, max_length=64)
    email: EmailStr | None = None
    director: str | None = Field(default=None, max_length=255)
    lat: float | None = Field(default=None, ge=-90, le=90)
    lon: float | None = Field(default=None, ge=-180, le=180)
    coords_verified: bool | None = None
    visible: bool | None = None
    translations: dict[str, BranchTrIn] | None = None


class BranchAdminOut(BaseModel):
    id: uuid.UUID
    slug: str
    type: str
    official_name: str | None
    phone: str | None
    email: str | None
    director: str | None
    lat: float | None
    lon: float | None
    coords_verified: bool
    visible: bool
    can_edit: bool
    can_edit_all_fields: bool
    translations: dict[str, dict[str, object]]


def _out(b: Branch, p: Principal) -> BranchAdminOut:
    any_ = p.has("branches.edit_any")
    return BranchAdminOut(
        id=b.id,
        slug=b.slug,
        type=b.type,
        official_name=b.official_name,
        phone=b.phone,
        email=b.email,
        director=b.director,
        lat=b.lat,
        lon=b.lon,
        coords_verified=b.coords_verified,
        visible=b.visible,
        can_edit=any_ or b.id in p.branch_ids,
        can_edit_all_fields=any_,
        translations=tr_dict(b, ["name", "short_name", "locality", "address", "hours", "description"]),
    )


@router.get("", response_model=list[BranchAdminOut])
async def list_branches(session: Session, p: Principal = Depends(STAFF)) -> list[BranchAdminOut]:
    stmt = select(Branch).order_by(Branch.sort_order)
    if not p.has("branches.edit_any"):
        stmt = stmt.where(Branch.id.in_(p.branch_ids))  # видит только свои
    return [_out(b, p) for b in (await session.execute(stmt)).scalars()]


@router.get("/{branch_id}", response_model=BranchAdminOut)
async def get_branch(
    branch_id: uuid.UUID, request: Request, session: Session, p: Principal = Depends(STAFF)
) -> BranchAdminOut:
    b = await get_or_404(session, Branch, branch_id, "Филиал")
    if not p.has("branches.edit_any") and b.id not in p.branch_ids:
        await deny(p, request, action="branch.read", entity="branch", entity_id=b.id)
    return _out(b, p)


@router.patch("/{branch_id}", response_model=BranchAdminOut)
async def update_branch(
    branch_id: uuid.UUID, body: BranchPatch, request: Request, session: Session, p: Principal = Depends(STAFF)
) -> BranchAdminOut:
    b = await get_or_404(session, Branch, branch_id, "Филиал")
    changes = body.model_dump(exclude_unset=True)
    # проверка на конкретный объект: свой филиал или право на все
    if not p.has("branches.edit_any"):
        if b.id not in p.branch_ids:
            await deny(
                p,
                request,
                action="branch.update",
                entity="branch",
                entity_id=b.id,
                message="Можно изменять только сведения своего филиала",
            )
        forbidden = set(changes) - OWN_FIELDS
        if forbidden:
            await deny(
                p,
                request,
                action="branch.update",
                entity="branch",
                entity_id=b.id,
                message=f"Недостаточно прав для полей: {', '.join(sorted(forbidden))}",
            )
    before = {k: getattr(b, k) for k in changes if k != "translations"}
    for key, value in changes.items():
        if key == "translations":
            for lang, tr in (body.translations or {}).items():
                upsert_translation(b, BranchTranslation, lang, tr.model_dump(exclude_unset=True))
        else:
            setattr(b, key, value)
    audit.record(
        session,
        action="branch.update",
        user_id=p.id,
        user_email=p.user.email,
        entity="branch",
        entity_id=b.id,
        request=request,
        details={"fields": sorted(changes), "before": {k: str(v) for k, v in before.items()}},
    )
    await session.commit()
    b = await reload(session, b)
    return _out(b, p)
