from __future__ import annotations

from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.block import Block


class BlockRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, blocker_id: int, blocked_id: int) -> None:
        existing = await self.session.scalar(
            select(Block).where(
                Block.blocker_id == blocker_id, Block.blocked_id == blocked_id
            )
        )
        if existing:
            return
        self.session.add(Block(blocker_id=blocker_id, blocked_id=blocked_id))

    async def remove(self, blocker_id: int, blocked_id: int) -> None:
        await self.session.execute(
            delete(Block).where(
                Block.blocker_id == blocker_id, Block.blocked_id == blocked_id
            )
        )

    async def list_for_user(self, blocker_id: int) -> list[int]:
        stmt = select(Block.blocked_id).where(Block.blocker_id == blocker_id)
        return list((await self.session.scalars(stmt)).all())

    async def is_blocked_pair(self, user_a: int, user_b: int) -> bool:
        stmt = select(Block).where(
            or_(
                (Block.blocker_id == user_a) & (Block.blocked_id == user_b),
                (Block.blocker_id == user_b) & (Block.blocked_id == user_a),
            )
        )
        return (await self.session.scalar(stmt)) is not None

