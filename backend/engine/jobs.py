from __future__ import annotations

import asyncio
import logging

from sqlmodel import Session

from app.database import engine

from .scheduler import ScheduleManager


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")


def _session_factory() -> Session:
    return Session(engine)


async def _serve() -> None:
    manager = ScheduleManager(session_factory=_session_factory)
    await manager.start()


def run() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    run()
