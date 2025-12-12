from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search import SearchRequest


class SearchRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create(
        self,
        user_id: int,
        language: str | None,
        min_age: int,
        max_age: int,
        modes: list[str],
    ) -> SearchRequest:
        req = SearchRequest(
            user_id=user_id,
            language=language,
            min_age=min_age,
            max_age=max_age,
            modes=modes or [],
            status="waiting",
        )
        self.session.add(req)
        return req

    async def set_status(self, request_id: int, status: str) -> None:
        await self.session.execute(
            update(SearchRequest).where(SearchRequest.id == request_id).values(status=status)
        )

    async def cancel_for_user(self, user_id: int) -> None:
        await self.session.execute(
            update(SearchRequest)
            .where(SearchRequest.user_id == user_id, SearchRequest.status == "waiting")
            .values(status="canceled")
        )

    async def delete_waiting_for_user(self, user_id: int) -> None:
        await self.session.execute(
            delete(SearchRequest).where(
                SearchRequest.user_id == user_id, SearchRequest.status == "waiting"
            )
        )

    async def list_waiting(self) -> list[SearchRequest]:
        stmt = select(SearchRequest).where(SearchRequest.status == "waiting")
        return list((await self.session.scalars(stmt)).all())

