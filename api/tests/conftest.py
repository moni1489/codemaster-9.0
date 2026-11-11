"""Тестовая среда: отдельная БД (TEST_DATABASE_URL), миграции Alembic, демо-сид с облегчёнными картинками."""

from __future__ import annotations

import asyncio
import io
import os
import subprocess
import sys
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings

API_DIR = Path(__file__).resolve().parents[1]
REPO = API_DIR.parent

_settings = Settings()
TEST_DB_URL = _settings.test_database_url
if not TEST_DB_URL:
    pytest.exit("TEST_DATABASE_URL не задан — см. .env.example", returncode=2)
if _settings.database_url == TEST_DB_URL:
    pytest.exit("TEST_DATABASE_URL совпадает с DATABASE_URL — тесты очищают БД, отказ", returncode=2)

_storage = Path(os.environ.get("TEST_STORAGE_DIR") or tempfile.mkdtemp(prefix="vko-test-storage-"))
os.environ["DATABASE_URL"] = TEST_DB_URL
os.environ["STORAGE_DIR"] = str(_storage)
os.environ["SEED_DIR"] = str(REPO / "seed")
os.environ.setdefault("SECRET_KEY", "test-secret-key-" + "x" * 32)
os.environ["COOKIE_SECURE"] = "false"
os.environ["LLM_PROVIDER"] = "rule"
get_settings.cache_clear()

from app.core import db as core_db  # noqa: E402
from app.main import create_app  # noqa: E402


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    # один цикл событий на всю сессию — движок SQLAlchemy общий
    for item in items:
        if asyncio.iscoroutinefunction(getattr(item, "function", None)):
            item.own_markers = [m for m in item.own_markers if m.name != "asyncio"]
            item.add_marker(pytest.mark.asyncio(loop_scope="session"))


def _tiny_render(kind: str, key: str, title: str, page: int = 1) -> bytes:
    img = Image.new("RGB", (64, 48), (200, 180, 150))
    out = io.BytesIO()
    img.save(out, "JPEG")
    return out.getvalue()


@pytest.fixture(scope="session")
async def seeded() -> AsyncIterator[dict[str, Any]]:
    engine = core_db.init_engine(TEST_DB_URL)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    env = {**os.environ, "DATABASE_URL": TEST_DB_URL, "PYTHONUTF8": "1"}
    proc = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=API_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr

    import app.seed.loader as loader

    loader.render = _tiny_render  # type: ignore[assignment]
    async with core_db.sessionmaker()() as session:
        result = await loader.seed_all(session)
    yield result
    await engine.dispose()


@pytest.fixture
async def session(seeded: dict[str, Any]) -> AsyncIterator[AsyncSession]:
    async with core_db.sessionmaker()() as s:
        yield s


@pytest.fixture
async def client(seeded: dict[str, Any]) -> AsyncIterator[AsyncClient]:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
