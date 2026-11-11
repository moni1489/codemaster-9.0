"""Настройки приложения. Все секреты — только из окружения (.env)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO = Path(__file__).resolve().parents[3]


def _repo_or(local: str, container: str) -> Path:
    """Путь внутри репозитория при локальном запуске, иначе — точка монтирования в контейнере."""
    candidate = _REPO / local
    return candidate if candidate.exists() else Path(container)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=("../.env", ".env"), env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field(default="postgresql+asyncpg://archive:archive@localhost:5432/archive")
    test_database_url: str | None = None

    secret_key: SecretStr = Field(default=SecretStr(""))
    session_idle_minutes: int = 30
    cookie_secure: bool = True
    login_rate_limit: str = "5/minute"

    site_url: str = "https://localhost"
    storage_dir: Path = Path("/data/storage")
    seed_dir: Path = Field(default_factory=lambda: _repo_or("seed", "/app/seed"))
    docs_source_dir: Path = Field(default_factory=lambda: _repo_or("docs/source", "/app/docs_source"))
    max_upload_mb: int = 50

    llm_provider: Literal["auto", "anthropic", "ollama", "rule"] = "auto"
    anthropic_api_key: SecretStr = Field(default=SecretStr(""))
    anthropic_model: str = "claude-sonnet-5-5"
    llm_timeout_seconds: float = 20.0
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"

    tesseract_cmd: str = "tesseract"
    ocr_langs: str = "rus+kaz+eng"

    def require_secret(self) -> str:
        value = self.secret_key.get_secret_value()
        if len(value) < 32:
            raise RuntimeError("SECRET_KEY не задан или короче 32 символов — см. .env.example")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
