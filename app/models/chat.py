from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user1_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    user2_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    offer_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("match_offers.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), default="active", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
