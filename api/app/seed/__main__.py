"""python -m app.seed — пересоздать демо-данные и вывести пароли демо-учёток (однократно, в консоль)."""

from __future__ import annotations

import asyncio
import time

from app.core.db import get_engine, sessionmaker
from app.seed.loader import seed_all


async def main() -> None:
    started = time.monotonic()
    async with sessionmaker()() as session:
        result = await seed_all(session)
    await get_engine().dispose()
    print(f"\nДемо-данные загружены за {time.monotonic() - started:.1f} с")
    print(f"  документов в каталоге: {result['documents']}, в публичном индексе: {result['indexed']}")
    print(f"  памятных дат: {result['memorial_dates']}")
    print("\nДемо-учётки (пароли показываются один раз и нигде не сохраняются):")
    for c in result["credentials"]:
        branch = f"  [филиал: {c.branch}]" if c.branch else ""
        print(f"  {c.role:<13} {c.email:<40} {c.password}{branch}")
    print("\nВход: /admin  ·  повторный запуск сида пересоздаёт данные и пароли.\n")


if __name__ == "__main__":
    asyncio.run(main())
