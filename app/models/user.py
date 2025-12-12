from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    roblox_nick: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    age: Mapped[int] = mapped_column(Integer, nullable=False)
    language: Mapped[str] = mapped_column(String(8), nullable=False, default="ru")
    modes: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    bio: Mapped[str] = mapped_column(Text, default="", nullable=False)
    avatar_file_id: Mapped[str | None] = mapped_column(String(256), nullable=True)

    last_search: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    state: Mapped[str] = mapped_column(String(16), default="idle", nullable=False)
    active_offer_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    active_chat_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    ban_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    ban_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    last_reengage_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

