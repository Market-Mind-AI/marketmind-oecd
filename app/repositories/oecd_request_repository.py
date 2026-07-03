import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.oecd_request import OECDRequest
from app.utils.time import utc_now


class OECDRequestRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        ingestion_run_id: uuid.UUID,
        endpoint: str,
        url: str,
        dataset_id: str | None = None,
        dataflow_id: str | None = None,
        structure_id: str | None = None,
        country: str | None = None,
        indicator_code: str | None = None,
        start_period: str | None = None,
        end_period: str | None = None,
        query_params: dict[str, Any] | None = None,
    ) -> OECDRequest:
        oecd_req = OECDRequest(
            id=uuid.uuid4(),
            ingestion_run_id=ingestion_run_id,
            endpoint=endpoint,
            url=url,
            dataset_id=dataset_id,
            dataflow_id=dataflow_id,
            structure_id=structure_id,
            country=country,
            indicator_code=indicator_code,
            start_period=start_period,
            end_period=end_period,
            query_params=query_params,
            created_at=utc_now(),
        )
        self._session.add(oecd_req)
        await self._session.flush()
        return oecd_req

    async def get_by_id(self, request_id: uuid.UUID) -> OECDRequest | None:
        result = await self._session.execute(select(OECDRequest).where(OECDRequest.id == request_id))
        return result.scalar_one_or_none()
