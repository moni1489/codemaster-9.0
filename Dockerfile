# Один контейнер для хостинга (Render): собранный фронтенд + API. Для полного стека с Caddy — docker-compose.yml.
FROM node:20-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY web/ .
RUN npm run build

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 UV_PROJECT_ENVIRONMENT=/opt/venv PATH="/opt/venv/bin:$PATH" \
    WEB_DIST_DIR=/app/web_dist STORAGE_DIR=/data/storage SEED_DIR=/app/seed DOCS_SOURCE_DIR=/app/docs_source
RUN apt-get update \
 && apt-get install -y --no-install-recommends fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.7 /uv /usr/local/bin/uv
WORKDIR /app
COPY api/pyproject.toml api/uv.lock ./
RUN uv sync --frozen --no-dev
COPY api/ .
COPY seed/ /app/seed/
COPY docs/source/ /app/docs_source/
COPY --from=web /web/dist /app/web_dist
RUN useradd --system --uid 10001 app && mkdir -p /data/storage && chown -R app /data/storage
USER app
EXPOSE 10000
# миграции → автосид при пустом хранилище (временный диск) → сервер на $PORT
CMD ["sh", "-c", "alembic upgrade head && python -m app.seed.auto && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*'"]
