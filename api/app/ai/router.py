"""Публичный эндпоинт ИИ-помощника. Не принимает заявления; запрос логируется обезличенно (без IP)."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.pipeline import ask
from app.ai.providers import get_provider
from app.core.db import get_session
from app.core.ratelimit import rate_limit
from app.models import SearchLog

router = APIRouter(prefix="/api/assistant", tags=["assistant"])


class AskIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    lang: str = Field(default="ru", pattern="^(kk|ru|en)$")


class AskOut(BaseModel):
    status: str
    text: str
    sources: list[dict[str, Any]]
    suggestions: list[str]
    intent: dict[str, Any]
    provider: str
    is_llm: bool
    degraded: bool
    removed_items: int
    disclaimer: str


@router.post("/ask", response_model=AskOut, dependencies=[Depends(rate_limit("20/minute", "assistant"))])
async def assistant_ask(body: AskIn, session: Annotated[AsyncSession, Depends(get_session)]) -> AskOut:
    answer = await ask(session, body.query.strip(), body.lang, get_provider())
    session.add(SearchLog(query=body.query.strip()[:300], lang=body.lang, source="assistant",
                          results_count=len(answer.sources)))  # fmt: skip
    await session.commit()
    return AskOut(**{k: getattr(answer, k) for k in AskOut.model_fields})


@router.get("/mode")
async def assistant_mode() -> dict[str, Any]:
    p = get_provider()
    return {"provider": p.name, "is_llm": p.is_llm}
