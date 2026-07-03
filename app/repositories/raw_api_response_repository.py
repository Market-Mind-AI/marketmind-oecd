import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.raw_api_response import RawApiResponse
from app.utils.time import utc_now


class RawApiResponseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        oecd_request_id: uuid.UUID,
        endpoint: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any] | list[Any],
    ) -> RawApiResponse:
        raw = RawApiResponse(
            id=uuid.uuid4(),
            oecd_request_id=oecd_request_id,
            endpoint=endpoint,
            request_payload=request_payload,
            response_payload=response_payload,  # type: ignore[arg-type]
            created_at=utc_now(),
        )
        self._session.add(raw)
        await self._session.flush()
        return raw
