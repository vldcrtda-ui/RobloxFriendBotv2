from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search import SearchRequest
from app.repositories.block_repo import BlockRepository
from app.repositories.offer_repo import OfferRepository
from app.repositories.search_repo import SearchRepository
from app.repositories.user_repo import UserRepository


class MatchingService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._recent_pairs: dict[tuple[int, int], float] = {}
        self.recent_ttl_sec = 1800

    async def enqueue(
        self,
        session: AsyncSession,
        user_id: int,
        language: str | None,
        min_age: int,
        max_age: int,
        modes: list[str],
    ) -> tuple[SearchRequest, int | None]:
        user_repo = UserRepository(session)
        search_repo = SearchRepository(session)

        user = await user_repo.get(user_id)
        if not user:
            raise ValueError("User not found")

        await search_repo.delete_waiting_for_user(user_id)
        req = await search_repo.create(user_id, language, min_age, max_age, modes)
        user.last_search = {
            "language": language,
            "min_age": min_age,
            "max_age": max_age,
            "modes": modes,
        }
        user.state = "searching"
        await session.flush()

        async with self._lock:
            offer_id = await self._try_match(session, req)
        return req, offer_id

    async def cancel_search(self, session: AsyncSession, user_id: int) -> None:
        user_repo = UserRepository(session)
        search_repo = SearchRepository(session)
        await search_repo.cancel_for_user(user_id)
        user = await user_repo.get(user_id)
        if user and user.state == "searching":
            user.state = "idle"
        await session.flush()

    async def _try_match(self, session: AsyncSession, req: SearchRequest) -> int | None:
        user_repo = UserRepository(session)
        block_repo = BlockRepository(session)
        search_repo = SearchRepository(session)
        offer_repo = OfferRepository(session)

        my_user = await user_repo.get(req.user_id)
        if not my_user:
            return None

        stmt = select(SearchRequest).where(SearchRequest.status == "waiting").order_by(SearchRequest.created_at.asc())
        waiting = list((await session.scalars(stmt)).all())

        for other_req in waiting:
            if other_req.user_id == req.user_id:
                continue
            if self._is_recent_pair(req.user_id, other_req.user_id):
                continue

            other_user = await user_repo.get(other_req.user_id)
            if not other_user or other_user.is_banned:
                continue

            if await block_repo.is_blocked_pair(req.user_id, other_req.user_id):
                continue

            if not self._compatible(my_user, req, other_user, other_req):
                continue

            offer = await offer_repo.create(
                req.user_id, other_req.user_id, req.id, other_req.id
            )

            req.status = "matched"
            other_req.status = "matched"

            my_user.state = "matching"
            other_user.state = "matching"
            my_user.active_offer_id = offer.id
            other_user.active_offer_id = offer.id

            await session.flush()
            return offer.id

        return None

    def mark_recent_pair(self, user_a: int, user_b: int) -> None:
        key = tuple(sorted((user_a, user_b)))
        self._recent_pairs[key] = asyncio.get_running_loop().time()

    def _is_recent_pair(self, user_a: int, user_b: int) -> bool:
        key = tuple(sorted((user_a, user_b)))
        ts = self._recent_pairs.get(key)
        if ts is None:
            return False
        if asyncio.get_running_loop().time() - ts > self.recent_ttl_sec:
            self._recent_pairs.pop(key, None)
            return False
        return True

    @staticmethod
    def _compatible(my_user, req, other_user, other_req) -> bool:
        if req.language and other_user.language != req.language:
            return False
        if other_req.language and my_user.language != other_req.language:
            return False

        if not (req.min_age <= other_user.age <= req.max_age):
            return False
        if not (other_req.min_age <= my_user.age <= other_req.max_age):
            return False

        if req.modes:
            if not set(req.modes) & set(other_user.modes):
                return False
        if other_req.modes:
            if not set(other_req.modes) & set(my_user.modes):
                return False

        return True


matching_service = MatchingService()
