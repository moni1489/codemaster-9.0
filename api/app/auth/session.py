"""Сессия админки: JWT (HS256) в httpOnly-cookie + CSRF double-submit, привязанный к токену (D-010).

- Скользящий срок: SESSION_IDLE_MINUTES неактивности → автовыход; токен перевыпускается при активности.
- Абсолютный предел жизни сессии: 8 часов с момента входа.
- CSRF: случайный токен хранится в claim `csrf` и в читаемой cookie; небезопасные запросы обязаны
  прислать его в заголовке X-CSRF-Token (сравнение constant-time с claim из подписанного JWT).
"""

from __future__ import annotations

import hmac
import secrets
import time
from dataclasses import dataclass

import jwt
from fastapi import Response

from app.core.config import get_settings

SESSION_COOKIE = "vko_session"
CSRF_COOKIE = "vko_csrf"
CSRF_HEADER = "x-csrf-token"
MAX_SESSION_SECONDS = 8 * 3600
ALGO = "HS256"


@dataclass(frozen=True)
class SessionClaims:
    user_id: str
    csrf: str
    auth_time: int
    exp: int


def issue(response: Response, user_id: str, *, csrf: str | None = None, auth_time: int | None = None) -> SessionClaims:
    settings = get_settings()
    now = int(time.time())
    claims = SessionClaims(
        user_id=user_id,
        csrf=csrf or secrets.token_urlsafe(24),
        auth_time=auth_time or now,
        exp=now + settings.session_idle_minutes * 60,
    )
    token = jwt.encode(
        {"sub": claims.user_id, "csrf": claims.csrf, "auth_time": claims.auth_time, "exp": claims.exp, "iat": now},
        settings.require_secret(),
        algorithm=ALGO,
    )
    max_age = settings.session_idle_minutes * 60
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=max_age,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/api",
    )
    response.set_cookie(
        CSRF_COOKIE,
        claims.csrf,
        max_age=max_age,
        httponly=False,
        secure=settings.cookie_secure,
        samesite="strict",
        path="/",
    )
    return claims


def clear(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/api")
    response.delete_cookie(CSRF_COOKIE, path="/")


def decode(token: str | None) -> SessionClaims | None:
    if not token:
        return None
    try:
        data = jwt.decode(
            token, get_settings().require_secret(), algorithms=[ALGO], options={"require": ["exp", "sub"]}
        )
    except jwt.PyJWTError:
        return None
    claims = SessionClaims(
        user_id=str(data["sub"]),
        csrf=str(data.get("csrf", "")),
        auth_time=int(data.get("auth_time", 0)),
        exp=int(data["exp"]),
    )
    if time.time() - claims.auth_time > MAX_SESSION_SECONDS:
        return None
    return claims


def csrf_ok(claims: SessionClaims, header_value: str | None) -> bool:
    return bool(header_value) and hmac.compare_digest(claims.csrf, header_value or "")
