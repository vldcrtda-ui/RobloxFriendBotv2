from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.db import init_db, close_db, SessionMaker
from app.handlers import start, profile, browse, search, chat, admin, admin_panel, common
from app.middlewares.activity import ActivityMiddleware
from app.middlewares.ban import BanMiddleware
from app.middlewares.db import DBSessionMiddleware
from app.services.reengage import ReengageService


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    bot = Bot(
        settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    dp.update.outer_middleware(DBSessionMiddleware(SessionMaker))
    dp.update.outer_middleware(ActivityMiddleware())
    dp.update.outer_middleware(BanMiddleware())

    dp.include_router(common.router)
    dp.include_router(admin.router)
    dp.include_router(admin_panel.router)
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(browse.router)
    dp.include_router(search.router)
    dp.include_router(chat.router)

    await init_db()

    reengage = ReengageService(bot)
    reengage.start()

    try:
        await dp.start_polling(bot)
    finally:
        reengage.stop()
        await close_db()


if __name__ == "__main__":
    asyncio.run(main())
