"""Автосид для хостинга с временным диском (Render free): если файлов нет — загрузить демо-данные."""

from __future__ import annotations

import asyncio

from app.core.db import get_engine, sessionmaker
from app.media import storage
from app.seed.loader import seed_all


async def main() -> None:
    masters = storage.root() / "master"
    if masters.exists() and any(masters.rglob("*.jpg")):
        print("autoseed: хранилище не пустое — пропуск")
        return
    print("autoseed: хранилище пустое — загрузка демо-данных…")
    async with sessionmaker()() as session:
        result = await seed_all(session)
    await get_engine().dispose()
    print(f"autoseed: готово, документов {result['documents']}, в индексе {result['indexed']}")


if __name__ == "__main__":
    asyncio.run(main())
