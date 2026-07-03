import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.oecd_dataflow import OECDDataflow
from app.utils.time import utc_now


class OECDDataflowRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_create(
        self, oecd_request_id: uuid.UUID, records: list[dict[str, Any]]
    ) -> list[OECDDataflow]:
        entities: list[OECDDataflow] = []
        now = utc_now()
        for record in records:
            entity = OECDDataflow(
                id=uuid.uuid4(),
                oecd_request_id=oecd_request_id,
                agency_id=record.get("agency_id"),
                dataflow_id=record.get("dataflow_id", ""),
                name=record.get("name"),
                description=record.get("description"),
                version=record.get("version"),
                is_final=record.get("is_final"),
                raw_payload=record.get("raw_payload"),
                created_at=now,
            )
            self._session.add(entity)
            entities.append(entity)
        await self._session.flush()
        return entities

    async def get_by_oecd_request_id(self, oecd_request_id: uuid.UUID) -> list[OECDDataflow]:
        result = await self._session.execute(
            select(OECDDataflow).where(OECDDataflow.oecd_request_id == oecd_request_id)
        )
        return list(result.scalars().all())
