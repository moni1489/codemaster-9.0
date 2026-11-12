# Государственный архив ВКО — прототип сайта

Демонстрационный прототип нового информационного сайта КГУ «Государственный архив Восточно-Казахстанской области»
(Code Masters Hackathon 9.0). Сайт **только информационный**: заявления, заказы и оплата на нём не принимаются.

**Что есть:** электронный каталог (фонд → опись → дело → документ) с поиском по 12 полям, синонимами и нечётким
поиском; просмотр открытых сканов, закрытые копии не выдаются ни через UI, ни через API; KZ/RU/EN; светлая/тёмная
тема; справочные разделы (госуслуга, платные услуги с прейскурантом, нормативка, комплаенс, читальный зал, FAQ,
новости); карта филиалов с маршрутами; онлайн-выставка; цифровая история; ИИ-помощник; админ-панель с ролями,
согласованием публикаций, версиями и журналом действий.

Документация: [архитектура](docs/ARCHITECTURE.md) · [интеграции](docs/INTEGRATIONS.md) · [инструкция редактора](docs/EDITOR_GUIDE.md)
· [готовность модулей](docs/READINESS.md) · [тестирование](docs/TESTING.md) · [сценарий показа](docs/DEMO_SCRIPT.md)
· [план](docs/PLAN.md) · [решения](docs/DECISIONS.md) · [источники демо-данных](seed/SOURCES.md)

## Запуск одной командой (Docker)

Требования: Docker Desktop / Docker Engine 24+ с Compose v2, `make` (или см. «без make»).

```bash
make up      # создаст .env из .env.example с секретом, соберёт и поднимет db, api, web, caddy
make seed    # загрузит демо-данные и ВЫВЕДЕТ ПАРОЛИ демо-учёток (один раз, в консоль)
```

Сайт: https://localhost (сертификат локальный — подтвердите в браузере) · админка: https://localhost/admin ·
OpenAPI: https://localhost/api/docs

Без `make`: `cp .env.example .env`, вписать `SECRET_KEY` (`python -c "import secrets;print(secrets.token_urlsafe(48))"`),
затем `docker compose up -d --build` и `docker compose exec api python -m app.seed`.

## Локальный запуск без Docker (Windows/macOS/Linux)

Требуется PostgreSQL 16 (расширения `pg_trgm`, `unaccent`; **локаль базы не `C`** — иначе нечёткий поиск не
работает с кириллицей), Python 3.12 + [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
python scripts/dev.py env       # .env с локальными значениями
# создать роль и БД archive / archive_test (команда печатается)
cd api && uv sync && cd ../web && npm ci && cd ..
python scripts/dev.py migrate
python scripts/dev.py seed      # демо-данные + пароли учёток
python scripts/dev.py up        # API :8000 + сайт :5173
python scripts/dev.py test      # pytest + vitest
python scripts/dev.py lint      # ruff + mypy + eslint + tsc
```

## Демо-учётки

`make seed` / `python scripts/dev.py seed` создаёт по одной учётке на роль (superadmin, site_admin, editor,
archivist, moderator, analyst) и двух администраторов филиалов (Риддер и Алтай). Пароли генерируются при каждом
запуске сида и печатаются в консоль; в репозитории их нет. Повторный сид пересоздаёт данные и пароли.

## Переменные окружения

| Переменная | Назначение | По умолчанию |
|---|---|---|
| `POSTGRES_USER/PASSWORD/DB` | учётка PostgreSQL в Docker | — |
| `DATABASE_URL`, `TEST_DATABASE_URL` | подключение к БД (asyncpg); тестовая БД очищается тестами | — |
| `SECRET_KEY` | подпись сессий (≥ 32 символа) | **обязательно** |
| `SESSION_IDLE_MINUTES` | автовыход из админки | 30 |
| `COOKIE_SECURE` | `true` за HTTPS | true |
| `LOGIN_RATE_LIMIT` | попыток входа с IP | 5/minute |
| `SITE_URL` | базовый адрес (sitemap) | https://localhost |
| `STORAGE_DIR`, `MAX_UPLOAD_MB` | хранилище файлов и лимит загрузки | /data/storage, 50 |
| `LLM_PROVIDER` | `auto` / `anthropic` / `openrouter` / `ollama` / `rule` | auto |
| `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL` | Claude (необязательно) | —, claude-opus-5-5 |
| `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` | бесплатные модели OpenRouter (необязательно) | — |
| `OLLAMA_URL`, `OLLAMA_MODEL` | локальная модель (необязательно) | — |
| `LLM_TIMEOUT_SECONDS` | таймаут ИИ | 45 |
| `TESSERACT_CMD`, `OCR_LANGS` | OCR (следующий этап) | tesseract, rus+kaz+eng |

Без ключей ИИ сайт полностью работает: помощник отвечает в детерминированном режиме (в UI — «демо-режим без LLM»).

## Структура

```
api/      FastAPI, SQLAlchemy 2 (async), Alembic, тесты pytest
web/      React 18 + Vite + TypeScript, Tailwind, тесты vitest
seed/     демо-данные (JSON) и генераторы из материалов заказчика (seed/tools)
infra/    Caddy (HTTPS, заголовки безопасности), init.sql
docs/     документация, исходные материалы заказчика (docs/source)
```
