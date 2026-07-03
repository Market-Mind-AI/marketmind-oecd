import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingestion_run import IngestionRun
from app.domain.enums import IngestionStatus
from app.utils.time import utc_now


class IngestionRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, source: str, request_payload: dict[str, Any]) -> IngestionRun:
        now = utc_now()
        run = IngestionRun(
            id=uuid.uuid4(),
            source=source,
            status=IngestionStatus.RUNNING,
            started_at=now,
            request_payload=request_payload,
            created_at=now,
        )
        self._session.add(run)
        await self._session.flush()
        return run

    async def mark_success(self, run: IngestionRun, execution_time_ms: int) -> IngestionRun:
        run.status = IngestionStatus.SUCCESS
        run.finished_at = utc_now()
        run.execution_time_ms = execution_time_ms
        await self._session.flush()
        return run

    async def mark_failed(self, run: IngestionRun, error_message: str, execution_time_ms: int) -> IngestionRun:
        run.status = IngestionStatus.FAILED
        run.finished_at = utc_now()
        run.execution_time_ms = execution_time_ms
        run.error_message = error_message
        await self._session.flush()
        return run

    async def get_by_id(self, run_id: uuid.UUID) -> IngestionRun | None:
        result = await self._session.execute(select(IngestionRun).where(IngestionRun.id == run_id))
        return result.scalar_one_or_none()
