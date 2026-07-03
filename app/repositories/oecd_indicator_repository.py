import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.oecd_indicator_catalog import OECDIndicatorCatalog
from app.utils.time import utc_now


class OECDIndicatorRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, records: list[dict[str, Any]]) -> list[OECDIndicatorCatalog]:
        entities: list[OECDIndicatorCatalog] = []
        now = utc_now()
        for record in records:
            existing = await self._get_by_code(record["indicator_code"])
            if existing:
                existing.indicator_name = record["indicator_name"]
                existing.description = record.get("description")
                existing.category = record["category"]
                existing.expected_unit = record.get("expected_unit")
                existing.marketmind_dimension = record.get("marketmind_dimension")
                existing.dataflow_id = record.get("dataflow_id")
                existing.dataset_id = record.get("dataset_id")
                existing.is_active = record.get("is_active", True)
                entities.append(existing)
            else:
                entity = OECDIndicatorCatalog(
                    id=uuid.uuid4(),
                    indicator_code=record["indicator_code"],
                    indicator_name=record["indicator_name"],
                    description=record.get("description"),
                    category=record["category"],
                    expected_unit=record.get("expected_unit"),
                    marketmind_dimension=record.get("marketmind_dimension"),
                    dataflow_id=record.get("dataflow_id"),
                    dataset_id=record.get("dataset_id"),
                    is_active=record.get("is_active", True),
                    created_at=now,
                )
                self._session.add(entity)
                entities.append(entity)
        await self._session.flush()
        return entities

    async def get_all(self, active_only: bool = False) -> list[OECDIndicatorCatalog]:
        stmt = select(OECDIndicatorCatalog)
        if active_only:
            stmt = stmt.where(OECDIndicatorCatalog.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_codes(self, codes: list[str]) -> list[OECDIndicatorCatalog]:
        result = await self._session.execute(
            select(OECDIndicatorCatalog).where(OECDIndicatorCatalog.indicator_code.in_(codes))
        )
        return list(result.scalars().all())

    async def _get_by_code(self, indicator_code: str) -> OECDIndicatorCatalog | None:
        result = await self._session.execute(
            select(OECDIndicatorCatalog).where(OECDIndicatorCatalog.indicator_code == indicator_code)
        )
        return result.scalar_one_or_none()
