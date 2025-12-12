from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.report import Report


class ReportRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def add(self, reporter_id: int, target_id: int, chat_id: int | None, reason: str, details: str | None) -> Report:
        rep = Report(
            reporter_id=reporter_id,
            target_id=target_id,
            chat_id=chat_id,
            reason=reason,
            details=details,
        )
        self.session.add(rep)
        return rep

    async def get(self, report_id: int) -> Report | None:
        return await self.session.get(Report, report_id)

    async def list_recent(self, limit: int = 20) -> list[Report]:
        stmt = select(Report).order_by(Report.id.desc()).limit(limit)
        return list((await self.session.scalars(stmt)).all())
