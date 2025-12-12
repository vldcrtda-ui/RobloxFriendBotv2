from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, user_id: int) -> User | None:
        return await self.session.get(User, user_id)

    async def get_by_nick(self, nick: str) -> User | None:
        nick = (nick or "").strip()
        if nick.startswith("@"):
            nick = nick[1:].strip()
        if not nick:
            return None
        stmt = select(User).where(func.lower(User.roblox_nick) == nick.lower())
        return await self.session.scalar(stmt)

    async def search_by_nick(self, query: str, limit: int = 10) -> list[User]:
        query = (query or "").strip()
        if query.startswith("@"):
            query = query[1:].strip()
        if not query:
            return []
        stmt = (
            select(User)
            .where(User.roblox_nick.ilike(f"%{query}%"))
            .order_by(User.roblox_nick.asc())
            .limit(limit)
        )
        return list((await self.session.scalars(stmt)).all())

    async def is_nick_taken(self, nick: str) -> bool:
        return (await self.get_by_nick(nick)) is not None

    async def create(
        self,
        user_id: int,
        roblox_nick: str,
        age: int,
        language: str,
        modes: list[str],
        bio: str,
        avatar_file_id: str | None,
    ) -> User:
        user = User(
            id=user_id,
            roblox_nick=roblox_nick,
            age=age,
            language=language,
            modes=modes,
            bio=bio,
            avatar_file_id=avatar_file_id,
            state="idle",
        )
        self.session.add(user)
        return user

    async def update_fields(self, user_id: int, **fields) -> None:
        stmt = update(User).where(User.id == user_id).values(**fields)
        await self.session.execute(stmt)

    async def delete(self, user_id: int) -> None:
        await self.session.execute(delete(User).where(User.id == user_id))

    async def touch(self, user_id: int, when: datetime) -> None:
        user = await self.get(user_id)
        if user:
            user.last_active_at = when

    async def set_ban(self, user_id: int, until: datetime | None, reason: str | None) -> None:
        await self.update_fields(
            user_id,
            is_banned=True,
            ban_until=until,
            ban_reason=reason,
            state="idle",
            active_chat_id=None,
            active_offer_id=None,
        )

    async def clear_ban(self, user_id: int) -> None:
        await self.update_fields(
            user_id, is_banned=False, ban_until=None, ban_reason=None
        )

    async def list_inactive(self, older_than: datetime, last_sent_before: datetime | None) -> list[User]:
        stmt = select(User).where(User.last_active_at < older_than, User.is_banned.is_(False))
        if last_sent_before:
            stmt = stmt.where(
                (User.last_reengage_sent_at.is_(None))
                | (User.last_reengage_sent_at < last_sent_before)
            )
        return list((await self.session.scalars(stmt)).all())
