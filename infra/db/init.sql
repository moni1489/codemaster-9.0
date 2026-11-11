-- Выполняется один раз при создании тома БД (docker-entrypoint-initdb.d).
-- Расширения также создаются миграцией (идемпотентно); здесь — для тестовой БД.
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
SELECT 'CREATE DATABASE ' || current_database() || '_test'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = current_database() || '_test')\gexec
