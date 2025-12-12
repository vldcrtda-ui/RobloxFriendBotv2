from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from aiogram import Bot

from app.config import settings
from app.db import SessionMaker
from app.repositories.user_repo import UserRepository
from app.utils.i18n import t


class ReengageService:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

    def start(self) -> None:
        self.scheduler.add_job(
            self._run_check,
            "interval",
            minutes=settings.reengage_check_interval_min,
            next_run_time=datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        self.scheduler.start()

    def stop(self) -> None:
        try:
            self.scheduler.shutdown(wait=False)
        except Exception:
            pass

    async def _run_check(self) -> None:
        async with SessionMaker() as session:
            repo = UserRepository(session)
            now = datetime.now(timezone.utc)
            older_than = now - timedelta(hours=settings.reengage_after_hours)
            last_sent_before = now - timedelta(hours=settings.reengage_after_hours)
            users = await repo.list_inactive(older_than, last_sent_before)

            for user in users:
                try:
                    await self.bot.send_message(
                        user.id,
                        t(user.language, "welcome_back") + "\n/search",
                    )
                    user.last_reengage_sent_at = now
                except Exception:
                    await asyncio.sleep(0)

            await session.commit()

