from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match_offer import MatchOffer


class OfferRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, offer_id: int) -> MatchOffer | None:
        return await self.session.get(MatchOffer, offer_id)

    async def create(
        self, user1_id: int, user2_id: int, search1_id: int | None, search2_id: int | None
    ) -> MatchOffer:
        offer = MatchOffer(
            user1_id=user1_id, user2_id=user2_id, search1_id=search1_id, search2_id=search2_id
        )
        self.session.add(offer)
        return offer

    async def set_status(self, offer_id: int, status: str) -> None:
        await self.session.execute(
            update(MatchOffer).where(MatchOffer.id == offer_id).values(status=status)
        )

    async def find_between(self, user_a: int, user_b: int) -> MatchOffer | None:
        stmt = select(MatchOffer).where(
            ((MatchOffer.user1_id == user_a) & (MatchOffer.user2_id == user_b))
            | ((MatchOffer.user1_id == user_b) & (MatchOffer.user2_id == user_a))
        ).order_by(MatchOffer.id.desc())
        return await self.session.scalar(stmt)

