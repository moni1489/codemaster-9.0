"""Фикстуры сотрудников для тестов админки и импорта (подключаются через pytest_plugins в conftest)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import session as sess
from app.core.db import sessionmaker
from app.core.ratelimit import limiter
from app.main import create_app
from app.seed.loader import create_user

PASSWORD = "Test-Password-123!"
STAFF = {
    "editor": ("t.editor@test.kz", None),
    "moderator": ("t.moderator@test.kz", None),
    "archivist": ("t.archivist@test.kz", None),
    "analyst": ("t.analyst@test.kz", None),
    "superadmin": ("t.super@test.kz", None),
    "branch_admin": ("t.ridder@test.kz", "ridder"),
    "branch_admin_altai": ("t.altai@test.kz", "altai"),
}


@pytest.fixture(scope="session")
async def staff(seeded: dict[str, Any]) -> dict[str, str]:
    async with sessionmaker()() as s:
        for key, (email, branch) in STAFF.items():
            role = "branch_admin" if key.startswith("branch_admin") else key
            await create_user(s, seeded["roles"], role, email, PASSWORD, seeded["branches"][branch] if branch else None)
        await s.commit()
    return {k: v[0] for k, v in STAFF.items()}


class Staff:
    def __init__(self, client: AsyncClient) -> None:
        self.c = client

    @property
    def csrf(self) -> dict[str, str]:
        return {"X-CSRF-Token": self.c.cookies.get(sess.CSRF_COOKIE) or ""}

    async def post(self, url: str, **kw: Any) -> Any:
        return await self.c.post(url, headers=self.csrf, **kw)

    async def patch(self, url: str, **kw: Any) -> Any:
        return await self.c.patch(url, headers=self.csrf, **kw)

    async def delete(self, url: str, **kw: Any) -> Any:
        return await self.c.delete(url, headers=self.csrf, **kw)

    async def get(self, url: str, **kw: Any) -> Any:
        return await self.c.get(url, **kw)


@pytest.fixture
async def login(staff: dict[str, str]) -> AsyncIterator[Any]:
    clients: list[AsyncClient] = []
    limiter.reset()

    async def _login(role: str) -> Staff:
        c = AsyncClient(transport=ASGITransport(app=create_app()), base_url="http://test")
        clients.append(c)
        r = await c.post("/api/auth/login", json={"email": staff[role], "password": PASSWORD})
        assert r.status_code == 200, r.text
        return Staff(c)

    yield _login
    for c in clients:
        await c.aclose()
    limiter.reset()
