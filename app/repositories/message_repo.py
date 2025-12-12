from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import ChatMessage


class MessageRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(
        self,
        chat_id: int,
        sender_id: int,
        content_type: str,
        text: str | None = None,
        file_id: str | None = None,
    ) -> ChatMessage:
        msg = ChatMessage(
            chat_id=chat_id,
            sender_id=sender_id,
            content_type=content_type,
            text=text,
            file_id=file_id,
        )
        self.session.add(msg)
        return msg

    async def list_for_chat(self, chat_id: int, limit: int = 50) -> list[ChatMessage]:
        stmt = (
            select(ChatMessage)
            .where(ChatMessage.chat_id == chat_id)
            .order_by(ChatMessage.id.desc())
            .limit(limit)
        )
        return list((await self.session.scalars(stmt)).all())

