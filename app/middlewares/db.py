from __future__ import annotations

from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


class DBSessionMiddleware(BaseMiddleware):
    def __init__(self, session_maker: async_sessionmaker[AsyncSession]):
        super().__init__()
        self.session_maker = session_maker

    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        async with self.session_maker() as session:
            data["session"] = session
            return await handler(event, data)

