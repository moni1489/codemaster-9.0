"""Хеширование паролей: argon2id (passlib)."""

from __future__ import annotations

from passlib.context import CryptContext

_ctx = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    return str(_ctx.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bool(_ctx.verify(password, password_hash))
    except (ValueError, TypeError):
        return False
