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

    async def last_collect_setup_by_country(self) -> dict[str, dict[str, Any]]:
        """Per country, what its successful collections asked for -- every indicator, from every run.

        A refresh replays what was asked before rather than composing a new
        request from scratch. The service already recorded exactly what a
        working collection looked like for that country, and replaying it needs
        no knowledge the service would otherwise have to keep -- which
        indicators that country was set up with, which dataflow they came from.

        Os indicadores são juntados de TODAS as execuções do país, não lidos da
        última. O Core pede um indicador por coleta, e replicar só o pedido mais
        recente renovava um indicador por país por noite -- os outros venciam e
        ficavam vencidos. É a regra que o UN Data já seguia, agora nos três.

        Only successful runs: replaying a request that failed would repeat the
        failure on a schedule.
        """
        payload = IngestionRun.request_payload
        country = payload["country"].astext
        stmt = (
            select(country, payload)
            .where(IngestionRun.status == IngestionStatus.SUCCESS)
            .where(country.is_not(None))
            .where(payload.has_key("indicator_codes"))
            .order_by(IngestionRun.started_at.desc())
        )
        setups: dict[str, dict[str, Any]] = {}
        for country_code, request_payload in (await self._session.execute(stmt)).all():
            setup = setups.setdefault(country_code, {**request_payload, "indicator_codes": []})
            for code in request_payload.get("indicator_codes") or []:
                if code not in setup["indicator_codes"]:
                    setup["indicator_codes"].append(code)
        return setups
