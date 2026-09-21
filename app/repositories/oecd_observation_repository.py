import uuid
from typing import Any

from sqlalchemy import func, select
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

    async def series(
        self,
        *,
        country: str,
        measure: str | None = None,
        indicator_code: str | None = None,
        frequency: str | None = None,
        limit: int | None = None,
    ) -> list[tuple[str, Any]]:
        """One value per time period, newest first, nulls dropped.

        Deduplicated on purpose, and this is not cosmetic. Re-collection inserts
        observations without replacing what is already stored, so a period ends
        up held many times over. A plain LIMIT 12 on the raw table returned
        twelve copies of the SAME quarter, which made the recent and the older
        window identical and produced a growth rate of exactly zero for every
        country -- a wrong number that looked entirely plausible.

        The values within a period are identical, so MAX picks that one value.
        The reader should not have to know this, which is why the deduplication
        happens here and not in whoever asks.

        frequency matters: a measure published both quarterly and annually
        carries both under one code, and mixing them silently breaks any window
        counted in periods.
        """
        inner = (
            select(
                OECDObservation.time_period.label("time_period"),
                func.max(OECDObservation.value).label("value"),
            )
            .where(OECDObservation.country == country)
            .where(OECDObservation.value.is_not(None))
            .group_by(OECDObservation.time_period)
        )
        if measure is not None:
            inner = inner.where(OECDObservation.measure == measure)
        if indicator_code is not None:
            inner = inner.where(OECDObservation.indicator_code == indicator_code)
        if frequency is not None:
            inner = inner.where(OECDObservation.frequency == frequency)

        subquery = inner.subquery()
        stmt = select(subquery.c.time_period, subquery.c.value).order_by(subquery.c.time_period.desc())
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]
