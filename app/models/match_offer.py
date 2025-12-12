from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class MatchOffer(Base):
    __tablename__ = "match_offers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user1_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    user2_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)

    search1_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("search_requests.id"), nullable=True)
    search2_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("search_requests.id"), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
