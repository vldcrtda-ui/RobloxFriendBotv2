from __future__ import annotations

from datetime import datetime

from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.chat import ChatSession


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(self, user1_id: int, user2_id: int, offer_id: int | None) -> ChatSession:
        chat = ChatSession(user1_id=user1_id, user2_id=user2_id, offer_id=offer_id, status="active")
        self.session.add(chat)
        return chat

    async def get_active_for_user(self, user_id: int) -> ChatSession | None:
        stmt = select(ChatSession).where(
            ChatSession.status == "active",
            or_(ChatSession.user1_id == user_id, ChatSession.user2_id == user_id),
        )
        return await self.session.scalar(stmt)

    async def close(self, chat_id: int, when: datetime) -> None:
        await self.session.execute(
            update(ChatSession)
            .where(ChatSession.id == chat_id)
            .values(status="closed", closed_at=when)
        )

    async def list_active(self) -> list[ChatSession]:
        stmt = select(ChatSession).where(ChatSession.status == "active")
        return list((await self.session.scalars(stmt)).all())

    async def list_recent(self, limit: int = 20, offset: int = 0) -> list[ChatSession]:
        stmt = select(ChatSession).order_by(ChatSession.id.desc()).offset(offset).limit(limit)
        return list((await self.session.scalars(stmt)).all())

    async def get(self, chat_id: int) -> ChatSession | None:
        return await self.session.get(ChatSession, chat_id)
