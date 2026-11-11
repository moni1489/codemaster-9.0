"""Кроссплатформенный запуск без Docker и make (Windows/macOS/Linux).

    python scripts/dev.py env        # создать .env из .env.example (локальные значения)
    python scripts/dev.py migrate    # alembic upgrade head
    python scripts/dev.py seed       # демо-данные + демо-учётки (пароли — в консоль)
    python scripts/dev.py up         # API :8000 + Vite :5173 (прокси /api)
    python scripts/dev.py test       # pytest + vitest
    python scripts/dev.py lint       # ruff + mypy + eslint + tsc

Требуется: локальный PostgreSQL 16 (pg_trgm, unaccent), uv, Node 20+.
"""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = ROOT / "api"
WEB = ROOT / "web"
NPM = "npm.cmd" if os.name == "nt" else "npm"
NPX = "npx.cmd" if os.name == "nt" else "npx"


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    print(f"$ {' '.join(cmd)}   (in {cwd.relative_to(ROOT) or '.'})", flush=True)
    res = subprocess.run(cmd, cwd=cwd, env=env, check=False)  # noqa: S603
    if res.returncode != 0:
        sys.exit(res.returncode)


def uv() -> str:
    found = shutil.which("uv")
    if not found:
        sys.exit("uv не найден: pip install uv")
    return found


def api_env() -> dict[str, str]:
    env = dict(os.environ)
    env_file = ROOT / ".env"
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip())
    env.setdefault("STORAGE_DIR", str(ROOT / "storage"))
    env.setdefault("SEED_DIR", str(ROOT / "seed"))
    env.setdefault("DOCS_SOURCE_DIR", str(ROOT / "docs" / "source"))
    env["PYTHONUTF8"] = "1"
    return env


def cmd_gen_secret() -> None:
    print(f"SECRET_KEY={secrets.token_urlsafe(48)}")


def cmd_env() -> None:
    target = ROOT / ".env"
    if target.exists():
        print(".env уже существует — не трогаю")
        return
    text = (ROOT / ".env.example").read_text(encoding="utf-8")
    pw = secrets.token_urlsafe(18)
    text = text.replace("change-me-strong-password", pw).replace("@db:5432", "@localhost:5432")
    text = text.replace("SECRET_KEY=\n", f"SECRET_KEY={secrets.token_urlsafe(48)}\n")
    text = text.replace("COOKIE_SECURE=true", "COOKIE_SECURE=false")
    text = text.replace("SITE_URL=https://localhost", "SITE_URL=http://localhost:5173")
    text = text.replace("STORAGE_DIR=/data/storage", f"STORAGE_DIR={(ROOT / 'storage').as_posix()}")
    target.write_text(text, encoding="utf-8")
    print(f".env создан. Пароль БД для роли archive: {pw}")
    print("Создайте роль и БД: CREATE ROLE archive LOGIN PASSWORD '...'; CREATE DATABASE archive OWNER archive;")


def cmd_migrate() -> None:
    run([uv(), "run", "alembic", "upgrade", "head"], API, api_env())


def cmd_seed() -> None:
    run([uv(), "run", "python", "-m", "app.seed"], API, api_env())


def cmd_up() -> None:
    env = api_env()
    api = subprocess.Popen(  # noqa: S603
        [uv(), "run", "uvicorn", "app.main:app", "--reload", "--port", "8000"], cwd=API, env=env
    )
    web = subprocess.Popen([NPM, "run", "dev"], cwd=WEB)  # noqa: S603
    print("API: http://localhost:8000/api/docs   Сайт: http://localhost:5173", flush=True)
    try:
        api.wait()
        web.wait()
    except KeyboardInterrupt:
        api.terminate()
        web.terminate()


def cmd_test() -> None:
    run([uv(), "run", "pytest", "-q"], API, api_env())
    run([NPM, "run", "test", "--silent"], WEB)


def cmd_lint() -> None:
    run([uv(), "run", "ruff", "check", "."], API)
    run([uv(), "run", "ruff", "format", "--check", "."], API)
    run([uv(), "run", "mypy", "app"], API)
    run([NPM, "run", "lint", "--silent"], WEB)
    run([NPM, "run", "typecheck", "--silent"], WEB)


def cmd_e2e() -> None:
    run([NPX, "playwright", "test"], WEB)


COMMANDS = {
    "gen-secret": cmd_gen_secret,
    "env": cmd_env,
    "migrate": cmd_migrate,
    "seed": cmd_seed,
    "up": cmd_up,
    "test": cmd_test,
    "lint": cmd_lint,
    "e2e": cmd_e2e,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]]()
