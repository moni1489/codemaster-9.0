"""Публичные эндпоинты ИИ-помощника. Не принимает заявления; запрос логируется обезличенно (без IP).

Голос: аудио записывается в браузере и распознаётся Groq Whisper на сервере (ключ только на сервере).
Аудио не сохраняется — передаётся провайдеру и сразу отбрасывается.
"""

from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.pipeline import ask
from app.ai.providers import get_provider
from app.core.config import get_settings
from app.core.db import get_session
from app.core.logging import log
from app.core.ratelimit import rate_limit
from app.models import SearchLog

router = APIRouter(prefix="/api/assistant", tags=["assistant"])
GROQ_STT_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MAX_AUDIO_BYTES = 8 * 1024 * 1024
# типичные «галлюцинации» Whisper на тишине/шуме
SILENCE_PHRASES = (
    "продолжение следует",
    "субтитры",
    "спасибо за просмотр",
    "thank you for watching",
    "thanks for watching",
)
AUDIO_MIMES = ("audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav", "audio/x-wav", "video/webm")


class AskIn(BaseModel):
    query: str = Field(min_length=2, max_length=500)
    lang: str = Field(default="ru", pattern="^(kk|ru|en)$")


class AskOut(BaseModel):
    status: str
    text: str
    speech: str
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
    session.add(
        SearchLog(query=body.query.strip()[:300], lang=body.lang, source="assistant", results_count=len(answer.sources))
    )
    await session.commit()
    return AskOut(**{k: getattr(answer, k) for k in AskOut.model_fields})


def stt_enabled() -> bool:
    return bool(get_settings().groq_api_key.get_secret_value())


@router.get("/mode")
async def assistant_mode() -> dict[str, Any]:
    p = get_provider()
    return {"provider": p.name, "is_llm": p.is_llm, "stt": stt_enabled(), "tts": tts_enabled()}


# ── Озвучка: нейроголоса Microsoft Edge через edge-tts (бесплатно, без ключа). Наружу уходит только текст ответа. ──
TTS_VOICES = {"ru": "ru-RU-SvetlanaNeural", "kk": "kk-KZ-AigulNeural", "en": "en-US-AvaNeural"}


def tts_enabled() -> bool:
    return get_settings().tts_provider == "edge"


class SpeakIn(BaseModel):
    text: str = Field(min_length=1, max_length=400)
    lang: str = Field(default="ru", pattern="^(kk|ru|en)$")


async def synthesize(text: str, lang: str) -> bytes:
    import edge_tts

    audio = bytearray()
    async for chunk in edge_tts.Communicate(text, TTS_VOICES[lang], rate="-5%").stream():
        if chunk["type"] == "audio":
            audio += chunk["data"]
    return bytes(audio)


@router.post("/speak", dependencies=[Depends(rate_limit("20/minute", "tts"))])
async def speak(body: SpeakIn) -> Response:
    if not tts_enabled():
        raise HTTPException(503, "Озвучка на сервере выключена")
    try:
        audio = await synthesize(body.text, body.lang)
    except Exception as exc:  # сервис недоступен → фронт переключится на голос браузера
        log.warning("tts_failed", error=type(exc).__name__)
        raise HTTPException(502, "Сервис озвучки недоступен") from exc
    if not audio:
        raise HTTPException(502, "Пустая озвучка")
    return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store"})


class TranscriptOut(BaseModel):
    text: str


@router.post("/transcribe", response_model=TranscriptOut, dependencies=[Depends(rate_limit("10/minute", "stt"))])
async def transcribe(audio: UploadFile = File(...), lang: str = Form("ru", pattern="^(kk|ru|en)$")) -> TranscriptOut:
    s = get_settings()
    if not stt_enabled():
        raise HTTPException(503, "Распознавание речи на сервере не настроено")
    mime = (audio.content_type or "").split(";")[0].strip().lower()
    if mime not in AUDIO_MIMES:
        raise HTTPException(415, "Неподдерживаемый формат аудио")
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(413, "Запись слишком длинная")
    if len(data) < 1000:
        raise HTTPException(422, "Пустая запись")
    ext = {"audio/ogg": "ogg", "audio/mp4": "m4a", "audio/mpeg": "mp3", "audio/wav": "wav", "audio/x-wav": "wav"}.get(
        mime, "webm"
    )
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(
                GROQ_STT_URL,
                headers={"Authorization": f"Bearer {s.groq_api_key.get_secret_value()}"},
                files={"file": (f"speech.{ext}", data, mime)},
                data={"model": s.groq_stt_model, "language": lang, "response_format": "json", "temperature": "0"},
            )
            r.raise_for_status()
            text = str(r.json().get("text", "")).strip()
    except httpx.HTTPError as exc:
        log.warning("stt_failed", error=type(exc).__name__)
        raise HTTPException(502, "Сервис распознавания речи недоступен — введите вопрос текстом") from exc
    if any(p in text.lower() for p in SILENCE_PHRASES) and len(text) < 60:
        text = ""
    return TranscriptOut(text=text[:500])
