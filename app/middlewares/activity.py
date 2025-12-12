from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware

from app.repositories.user_repo import UserRepository


class ActivityMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        session = data.get("session")
        user_id = getattr(getattr(event, "from_user", None), "id", None)
        if session and user_id:
            repo = UserRepository(session)
            await repo.touch(user_id, datetime.now(timezone.utc))
            await session.commit()
        return await handler(event, data)

