from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.models.base import Base

engine: AsyncEngine = create_async_engine(settings.database_url, echo=False, future=True)
SessionMaker = async_sessionmaker(engine, expire_on_commit=False)

logger = logging.getLogger(__name__)


async def init_db(retries: int = 30, delay_s: float = 1.0) -> None:
    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            return
        except OperationalError as exc:
            last_exc = exc
            if attempt >= retries:
                break
            logger.warning("DB not ready (%s/%s), retrying in %.1fs", attempt, retries, delay_s)
            await asyncio.sleep(delay_s)
            delay_s = min(delay_s * 1.5, 10.0)

    assert last_exc is not None
    raise last_exc


async def close_db() -> None:
    await engine.dispose()
