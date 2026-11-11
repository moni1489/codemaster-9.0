"""Ограничение частоты запросов на базе `limits` (ядро slowapi), оформленное как зависимость FastAPI.

Используется для входа в админку, отзывов и ИИ-помощника. Хранилище — в памяти процесса; для нескольких
воркеров в проде — Redis (`limits.storage.RedisStorage`), см. docs/ARCHITECTURE.md.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import HTTPException, Request
from limits import parse
from limits.storage import MemoryStorage
from limits.strategies import MovingWindowRateLimiter


class RateLimiter:
    def __init__(self) -> None:
        self.storage = MemoryStorage()
        self.strategy = MovingWindowRateLimiter(self.storage)

    def hit(self, spec: str, *keys: str) -> bool:
        return self.strategy.hit(parse(spec), *keys)

    def reset(self) -> None:
        self.storage.reset()


limiter = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def rate_limit(spec: str, scope: str) -> Callable[[Request], None]:
    def dependency(request: Request) -> None:
        if not limiter.hit(spec, scope, client_ip(request)):
            raise HTTPException(429, "Слишком много запросов. Повторите попытку позже.")

    return dependency
