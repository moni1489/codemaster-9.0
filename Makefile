# Каноничный запуск — Docker Compose. На Windows без make используйте
# эквивалент: python scripts/dev.py <цель>  (см. README).

COMPOSE ?= docker compose
API     = $(COMPOSE) exec -T api

.PHONY: up down logs seed test test-api test-web e2e lint fmt env

env:
	@test -f .env || (cp .env.example .env && python3 scripts/dev.py gen-secret >> .env && echo ".env создан из .env.example")

up: env
	$(COMPOSE) up -d --build
	@echo "Сайт: https://localhost  (API: https://localhost/api/docs)"

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

# Создаёт демо-данные и демо-учётки; пароли печатаются в консоль один раз.
seed:
	$(API) python -m app.seed

test: test-api test-web

test-api:
	$(API) sh -c "uv sync --frozen >/dev/null && pytest -q"

test-web:
	cd web && npm ci --silent && npm run test --silent

e2e:
	cd web && npx playwright test

lint:
	$(API) sh -c "uv sync --frozen >/dev/null && ruff check . && ruff format --check . && mypy app"
	cd web && npm run lint && npm run typecheck

fmt:
	$(API) sh -c "ruff format . && ruff check --fix ."
