import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.oecd_observation import OECDObservation
from app.utils.time import utc_now


class OECDObservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_create(
        self, oecd_request_id: uuid.UUID, records: list[dict[str, Any]]
    ) -> list[OECDObservation]:
        entities: list[OECDObservation] = []
        now = utc_now()
        for record in records:
            entity = OECDObservation(
                id=uuid.uuid4(),
                oecd_request_id=oecd_request_id,
                dataset_id=record.get("dataset_id"),
                dataflow_id=record.get("dataflow_id"),
                country=record.get("country", ""),
                indicator_code=record.get("indicator_code", ""),
                indicator_name=record.get("indicator_name"),
                measure=record.get("measure"),
                unit=record.get("unit"),
                frequency=record.get("frequency"),
                time_period=record.get("time_period", ""),
                value=record.get("value"),
                normalized_value=record.get("normalized_value"),
                attributes=record.get("attributes"),
                created_at=now,
            )
            self._session.add(entity)
            entities.append(entity)
        await self._session.flush()
        return entities

    async def get_by_oecd_request_id(self, oecd_request_id: uuid.UUID) -> list[OECDObservation]:
        result = await self._session.execute(
            select(OECDObservation).where(OECDObservation.oecd_request_id == oecd_request_id)
        )
        return list(result.scalars().all())
