from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable, Awaitable, Any

from aiogram import BaseMiddleware

from app.config import settings
from app.repositories.user_repo import UserRepository


class BanMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Any, dict[str, Any]], Awaitable[Any]],
        event: Any,
        data: dict[str, Any],
    ) -> Any:
        session = data.get("session")
        if session is None:
            return await handler(event, data)

        user_id = getattr(getattr(event, "from_user", None), "id", None)
        if user_id is None:
            return await handler(event, data)

        if user_id in settings.admin_id_set:
            return await handler(event, data)

        repo = UserRepository(session)
        user = await repo.get(user_id)
        if not user or not user.is_banned:
            return await handler(event, data)

        now = datetime.now(timezone.utc)
        if user.ban_until and user.ban_until <= now:
            await repo.clear_ban(user_id)
            await session.commit()
            return await handler(event, data)

        text = "Вы в бане"
        if user.ban_until:
            text += f" до {user.ban_until:%Y-%m-%d %H:%M} UTC"
        if user.ban_reason:
            text += f"\nПричина: {user.ban_reason}"

        bot = data.get("bot")
        if bot and hasattr(event, "chat"):
            await bot.send_message(event.chat.id, text)
        return None

