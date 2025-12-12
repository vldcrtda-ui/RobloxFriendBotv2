from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.block_repo import BlockRepository
from app.repositories.chat_repo import ChatRepository
from app.repositories.offer_repo import OfferRepository
from app.repositories.search_repo import SearchRepository
from app.repositories.user_repo import UserRepository


class OfferService:
    async def propose_chat(self, session: AsyncSession, offer_id: int, proposer_id: int) -> int | None:
        offer_repo = OfferRepository(session)
        user_repo = UserRepository(session)
        chat_repo = ChatRepository(session)

        offer = await offer_repo.get(offer_id)
        if not offer or offer.status in {"declined", "blocked", "active"}:
            return None

        if proposer_id not in {offer.user1_id, offer.user2_id}:
            return None

        if proposer_id == offer.user1_id:
            if offer.status == "offered2":
                return await self._activate(session, offer_id)
            offer.status = "offered1"
        else:
            if offer.status == "offered1":
                return await self._activate(session, offer_id)
            offer.status = "offered2"

        await session.flush()
        return None

    async def decline(self, session: AsyncSession, offer_id: int, decliner_id: int) -> None:
        offer_repo = OfferRepository(session)
        user_repo = UserRepository(session)
        search_repo = SearchRepository(session)

        offer = await offer_repo.get(offer_id)
        if not offer or offer.status in {"declined", "blocked", "active"}:
            return

        offer.status = "declined"
        try:
            from app.services.matching import matching_service

            matching_service.mark_recent_pair(offer.user1_id, offer.user2_id)
        except Exception:
            pass

        for uid in (offer.user1_id, offer.user2_id):
            user = await user_repo.get(uid)
            if user:
                user.active_offer_id = None
                if user.state == "matching":
                    user.state = "idle"

        if offer.search1_id:
            await search_repo.set_status(offer.search1_id, "declined")
        if offer.search2_id:
            await search_repo.set_status(offer.search2_id, "declined")

        await session.flush()

    async def block_pair(self, session: AsyncSession, offer_id: int, blocker_id: int) -> int | None:
        offer_repo = OfferRepository(session)
        user_repo = UserRepository(session)
        block_repo = BlockRepository(session)

        offer = await offer_repo.get(offer_id)
        if not offer:
            return None

        target_id = offer.user2_id if blocker_id == offer.user1_id else offer.user1_id
        await block_repo.add(blocker_id, target_id)

        offer.status = "blocked"
        try:
            from app.services.matching import matching_service

            matching_service.mark_recent_pair(offer.user1_id, offer.user2_id)
        except Exception:
            pass

        for uid in (offer.user1_id, offer.user2_id):
            user = await user_repo.get(uid)
            if user:
                user.active_offer_id = None
                if user.state == "matching":
                    user.state = "idle"

        await session.flush()
        return target_id

    async def _activate(self, session: AsyncSession, offer_id: int) -> int:
        offer_repo = OfferRepository(session)
        user_repo = UserRepository(session)
        chat_repo = ChatRepository(session)

        offer = await offer_repo.get(offer_id)
        if not offer:
            raise ValueError("Offer not found")

        chat = await chat_repo.create(offer.user1_id, offer.user2_id, offer.id)
        offer.status = "active"

        for uid in (offer.user1_id, offer.user2_id):
            user = await user_repo.get(uid)
            if user:
                user.state = "chatting"
                user.active_chat_id = chat.id
                user.active_offer_id = None

        await session.flush()
        return chat.id

    async def close_chat_for_user(self, session: AsyncSession, user_id: int) -> int | None:
        user_repo = UserRepository(session)
        chat_repo = ChatRepository(session)

        user = await user_repo.get(user_id)
        if not user or user.state != "chatting" or not user.active_chat_id:
            return None

        chat_id = user.active_chat_id
        chat = await chat_repo.get_active_for_user(user_id)
        if not chat:
            user.active_chat_id = None
            user.state = "idle"
            return None

        await chat_repo.close(chat_id, datetime.now(timezone.utc))

        for uid in (chat.user1_id, chat.user2_id):
            u = await user_repo.get(uid)
            if u:
                u.state = "idle"
                u.active_chat_id = None

        await session.flush()
        return chat_id


offer_service = OfferService()
