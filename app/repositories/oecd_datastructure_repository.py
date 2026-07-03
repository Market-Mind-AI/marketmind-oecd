import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.oecd_datastructure import OECDDatastructure
from app.utils.time import utc_now


class OECDDatastructureRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_create(
        self, oecd_request_id: uuid.UUID, records: list[dict[str, Any]]
    ) -> list[OECDDatastructure]:
        entities: list[OECDDatastructure] = []
        now = utc_now()
        for record in records:
            entity = OECDDatastructure(
                id=uuid.uuid4(),
                oecd_request_id=oecd_request_id,
                dataflow_id=record.get("dataflow_id"),
                structure_id=record.get("structure_id"),
                dimension_id=record.get("dimension_id"),
                dimension_name=record.get("dimension_name"),
                dimension_position=record.get("dimension_position"),
                code_id=record.get("code_id"),
                code_name=record.get("code_name"),
                raw_payload=record.get("raw_payload"),
                created_at=now,
            )
            self._session.add(entity)
            entities.append(entity)
        await self._session.flush()
        return entities

    async def get_by_oecd_request_id(self, oecd_request_id: uuid.UUID) -> list[OECDDatastructure]:
        result = await self._session.execute(
            select(OECDDatastructure).where(OECDDatastructure.oecd_request_id == oecd_request_id)
        )
        return list(result.scalars().all())
