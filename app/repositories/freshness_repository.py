from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingestion_run import IngestionRun
from app.db.models.oecd_observation import OECDObservation
from app.db.models.oecd_request import OECDRequest

Pair = tuple[str, str]

# A check is a collection that FINISHED. A request whose run failed asked and
# got nothing back -- the source was down -- and counting it as a check made a
# 50-minute UN Data outage (22/10/2026) report twenty pairs as fresh for the
# whole window, with their last real data a month old. A run still in flight is
# not a check yet either.
CHECKED_STATUSES = ("success", "partial")


@dataclass(frozen=True)
class ObservationFacts:
    last_observation_at: datetime
    latest_period: str | None
    observation_count: int


class FreshnessRepository:
    """Answers "when did we last look at this?", per country and indicator.

    Two separate questions, deliberately not one join. A CHECK is a request we
    made (oecd_requests), and it happened whether or not the OECD had anything
    to give back. An OBSERVATION is data that landed. Reading freshness off
    observations alone would report a country the source genuinely has no data
    for as "never checked" forever, and it would be re-fetched every day.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def last_checks(
        self, *, countries: list[str] | None = None, indicators: list[str] | None = None
    ) -> dict[Pair, datetime]:
        stmt = (
            select(OECDRequest.country, OECDRequest.indicator_code, func.max(OECDRequest.created_at))
            .join(IngestionRun, IngestionRun.id == OECDRequest.ingestion_run_id)
            .where(IngestionRun.status.in_(CHECKED_STATUSES))
            .where(OECDRequest.country.is_not(None))
            .where(OECDRequest.indicator_code.is_not(None))
            .group_by(OECDRequest.country, OECDRequest.indicator_code)
        )
        if countries:
            stmt = stmt.where(OECDRequest.country.in_(countries))
        if indicators:
            stmt = stmt.where(OECDRequest.indicator_code.in_(indicators))

        result = await self._session.execute(stmt)
        return {(row[0], row[1]): row[2] for row in result.all()}

    async def observation_facts(
        self, *, countries: list[str] | None = None, indicators: list[str] | None = None
    ) -> dict[Pair, ObservationFacts]:
        stmt = select(
            OECDObservation.country,
            OECDObservation.indicator_code,
            func.max(OECDObservation.created_at),
            func.max(OECDObservation.time_period),
            func.count(),
        ).group_by(OECDObservation.country, OECDObservation.indicator_code)
        if countries:
            stmt = stmt.where(OECDObservation.country.in_(countries))
        if indicators:
            stmt = stmt.where(OECDObservation.indicator_code.in_(indicators))

        result = await self._session.execute(stmt)
        return {
            (row[0], row[1]): ObservationFacts(
                last_observation_at=row[2], latest_period=row[3], observation_count=row[4]
            )
            for row in result.all()
        }
