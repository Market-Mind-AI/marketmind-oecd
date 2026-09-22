from datetime import timedelta
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.oecd_client import OECDClient
from app.core.exceptions import IndicatorNotConfiguredError
from app.core.logging import logger
from app.domain.enums import IngestionStatus, OECDEndpoint
from app.repositories.freshness_repository import FreshnessRepository
from app.repositories.ingestion_run_repository import IngestionRunRepository
from app.repositories.oecd_dataflow_repository import OECDDataflowRepository
from app.repositories.oecd_datastructure_repository import OECDDatastructureRepository
from app.repositories.oecd_indicator_repository import OECDIndicatorRepository
from app.repositories.oecd_observation_repository import OECDObservationRepository
from app.repositories.oecd_request_repository import OECDRequestRepository
from app.repositories.raw_api_response_repository import RawApiResponseRepository
from app.schemas.requests import (
    DataflowsRequest,
    DatastructureRequest,
    IndicatorCatalogItem,
    IndicatorCatalogRequest,
    IndicatorCollectRequest,
    ObservationsRequest,
    RefreshStaleRequest,
)
from app.schemas.responses import (
    CodeItem,
    DataflowItem,
    DataflowsData,
    DataflowsResponse,
    DatastructureData,
    DatastructureResponse,
    DimensionItem,
    FreshnessData,
    FreshnessItem,
    FreshnessResponse,
    IndicatorCatalogItemResponse,
    IndicatorCatalogResponse,
    IndicatorCollectData,
    IndicatorCollectResponse,
    Metadata,
    ObservationItem,
    ObservationsData,
    ObservationsResponse,
    RefreshedCountry,
    RefreshStaleData,
    RefreshStaleResponse,
    SeriesData,
    SeriesPoint,
    SeriesResponse,
)
from app.utils.normalization import normalize_observations
from app.utils.sdmx import extract_dataflows, extract_dimensions, extract_observations
from app.utils.time import as_naive_utc, elapsed_ms, utc_now

# Known SDMX series-dimension order per dataflow (REF_AREA/MEASURE positions +
# total dimension count), used to build a scoped query_key for
# collect_indicators instead of always fetching the entire dataflow (every
# country, every series) and filtering client-side. Confirmed against the
# real OECD API (GET /dataflow/{agency}/{dataflow_id}), not guessed — see
# marketmind-core's investigation (2026-07-03) that found collect_indicators
# always requesting key="all", which for DSD_PRICES@DF_PRICES_ALL fetches a
# dataset large enough to routinely time out or take over an hour for a
# single country. Extend this map when adding a new dataflow to the catalog;
# dataflows not listed here fall back to the previous "all" behavior.
_SERIES_KEY_LAYOUT: dict[str, dict[str, int]] = {
    "DSD_PRICES@DF_PRICES_ALL": {
        "REF_AREA": 0,
        "FREQ": 1,
        "METHODOLOGY": 2,
        "MEASURE": 3,
        "UNIT_MEASURE": 4,
        "EXPENDITURE": 5,
        "ADJUSTMENT": 6,
        "TRANSFORMATION": 7,
    },  # fmt: skip
    # Confirmed 2026-07-08 against the real OECD API (agency OECD.ECO.MPD;
    # the /data endpoint itself needs no agency prefix, only /dataflow
    # structure discovery does) — "Analytical house prices indicators",
    # MEASURE=RHP is "Real house price indices". Backs REAL_ESTATE_GROWTH_SCORE
    # (marketmind-core Cap. 4 §4.4.3).
    "DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES": {
        "REF_AREA": 0,
        "FREQ": 1,
        "MEASURE": 2,
        "UNIT_MEASURE": 3,
    },  # fmt: skip
}

# Mirrors what was live in the indicator catalog as of 2026-07-08 (until
# then, entries only ever got there via manual POST /indicators/catalog
# calls, with no code-level record of them — the RHP addition earlier that
# same day would have been silently lost on the next fresh volume without
# this). UNEMP/CCI keep dataflow_id=None exactly as they were live: neither
# is wired to a real dataflow yet, so collect_indicators still rejects them
# with "missing dataflow_id" until someone does that investigation, same
# as before this list existed.
SEED_INDICATORS: list[dict[str, Any]] = [
    {
        "indicator_code": "CPI",
        "indicator_name": "Consumer Price Index",
        "description": "Measures inflation via consumer prices.",
        "category": "inflation",
        "expected_unit": "percentage",
        "marketmind_dimension": "macroeconomic_risk",
        "dataflow_id": "DSD_PRICES@DF_PRICES_ALL",
    },
    {
        "indicator_code": "UNEMP",
        "indicator_name": "Unemployment Rate",
        "description": "Harmonised unemployment rate.",
        "category": "unemployment",
        "expected_unit": "percentage",
        "marketmind_dimension": "macroeconomic_risk",
    },
    {
        "indicator_code": "CCI",
        "indicator_name": "Consumer Confidence Indicator",
        "description": "OECD composite consumer confidence indicator.",
        "category": "consumer_confidence",
        "expected_unit": "index",
        "marketmind_dimension": "economic_readiness",
    },
    {
        "indicator_code": "RHP",
        "indicator_name": "Real House Price Index",
        "description": (
            "OECD Analytical house price indicators — real (inflation-adjusted) house price "
            "index, quarterly, rebased to 100 per country per base year."
        ),
        "category": "real_estate",
        "expected_unit": "index",
        "marketmind_dimension": "economic_readiness",
        "dataflow_id": "DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES",
    },
]


def _build_series_key(dataflow_id: str, country: str, measure: str) -> str | None:
    """Returns a positional SDMX key scoping REF_AREA=country and
    MEASURE=measure (wildcarding every other dimension), or None if this
    dataflow's dimension layout isn't known yet (caller falls back to "all")."""
    layout = _SERIES_KEY_LAYOUT.get(dataflow_id)
    if layout is None:
        return None
    size = len(layout)
    segments = [""] * size
    segments[layout["REF_AREA"]] = country
    segments[layout["MEASURE"]] = measure
    return ".".join(segments)


class OECDService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._client = OECDClient()
        self._ingestion_repo = IngestionRunRepository(session)
        self._oecd_request_repo = OECDRequestRepository(session)
        self._raw_response_repo = RawApiResponseRepository(session)
        self._dataflow_repo = OECDDataflowRepository(session)
        self._datastructure_repo = OECDDatastructureRepository(session)
        self._observation_repo = OECDObservationRepository(session)
        self._indicator_repo = OECDIndicatorRepository(session)
        self._freshness_repo = FreshnessRepository(session)

    async def collect_dataflows(self, request: DataflowsRequest) -> DataflowsResponse:
        endpoint = OECDEndpoint.DATAFLOWS
        start = utc_now()
        run = await self._ingestion_repo.create(source="oecd", request_payload=request.model_dump())
        try:
            data, url = await self._client.get_dataflows(
                agency_id=request.agency_id,
                detail=request.detail,
            )
            oecd_req = await self._oecd_request_repo.create(
                ingestion_run_id=run.id,
                endpoint=endpoint,
                url=url,
            )
            await self._raw_response_repo.create(
                oecd_request_id=oecd_req.id,
                endpoint=endpoint,
                request_payload=request.model_dump(),
                response_payload=data,
            )
            parsed = extract_dataflows(data)
            await self._dataflow_repo.bulk_create(oecd_request_id=oecd_req.id, records=parsed)

            exec_time = elapsed_ms(start)
            await self._ingestion_repo.mark_success(run, exec_time)
            await self._session.commit()

            self._log_success(
                endpoint=endpoint,
                run_id=run.id,
                request_id=oecd_req.id,
                exec_time=exec_time,
                records=len(parsed),
            )

            return DataflowsResponse(
                request=request.model_dump(),
                metadata=self._meta(endpoint, exec_time, len(parsed), run.id, oecd_req.id),
                data=DataflowsData(
                    dataflows=[
                        DataflowItem(
                            agency_id=df.get("agency_id"),
                            dataflow_id=df["dataflow_id"],
                            name=df.get("name"),
                            description=df.get("description"),
                            version=df.get("version"),
                        )
                        for df in parsed
                    ]
                ),
            )
        except Exception as e:
            await self._fail(run, endpoint, start, e)
            raise

    async def collect_datastructure(self, request: DatastructureRequest) -> DatastructureResponse:
        endpoint = OECDEndpoint.DATASTRUCTURE
        start = utc_now()
        run = await self._ingestion_repo.create(source="oecd", request_payload=request.model_dump())
        try:
            data, url = await self._client.get_datastructure(
                agency_id=request.agency_id,
                dataflow_id=request.dataflow_id,
                structure_id=request.structure_id,
            )
            oecd_req = await self._oecd_request_repo.create(
                ingestion_run_id=run.id,
                endpoint=endpoint,
                url=url,
                dataflow_id=request.dataflow_id,
                structure_id=request.structure_id,
            )
            await self._raw_response_repo.create(
                oecd_request_id=oecd_req.id,
                endpoint=endpoint,
                request_payload=request.model_dump(),
                response_payload=data,
            )
            parsed = extract_dimensions(data, dataflow_id=request.dataflow_id)
            await self._datastructure_repo.bulk_create(oecd_request_id=oecd_req.id, records=parsed)

            dimensions_grouped = self._group_dimensions(parsed)
            exec_time = elapsed_ms(start)
            await self._ingestion_repo.mark_success(run, exec_time)
            await self._session.commit()

            self._log_success(
                endpoint=endpoint,
                run_id=run.id,
                request_id=oecd_req.id,
                exec_time=exec_time,
                records=len(parsed),
            )

            return DatastructureResponse(
                request=request.model_dump(),
                metadata=self._meta(endpoint, exec_time, len(dimensions_grouped), run.id, oecd_req.id),
                data=DatastructureData(dimensions=dimensions_grouped),
            )
        except Exception as e:
            await self._fail(run, endpoint, start, e)
            raise

    async def collect_observations(self, request: ObservationsRequest) -> ObservationsResponse:
        endpoint = OECDEndpoint.OBSERVATIONS
        start = utc_now()
        run = await self._ingestion_repo.create(source="oecd", request_payload=request.model_dump())
        try:
            query_params: dict[str, str] = {}
            if request.start_period:
                query_params["startPeriod"] = request.start_period
            if request.end_period:
                query_params["endPeriod"] = request.end_period
            if request.query_params:
                query_params.update(request.query_params)

            data, url = await self._client.get_observations(
                dataflow_id=request.dataflow_id,
                query_key=request.query_key,
                query_params=query_params if query_params else None,
            )
            oecd_req = await self._oecd_request_repo.create(
                ingestion_run_id=run.id,
                endpoint=endpoint,
                url=url,
                dataset_id=request.dataset_id,
                dataflow_id=request.dataflow_id,
                country=request.country,
                indicator_code=request.indicator_code,
                start_period=request.start_period,
                end_period=request.end_period,
                query_params=query_params if query_params else None,
            )
            await self._raw_response_repo.create(
                oecd_request_id=oecd_req.id,
                endpoint=endpoint,
                request_payload=request.model_dump(),
                response_payload=data,
            )
            raw_obs = extract_observations(
                data,
                country=request.country,
                indicator_code=request.indicator_code,
                dataflow_id=request.dataflow_id,
                dataset_id=request.dataset_id,
            )
            normalized = normalize_observations(raw_obs)
            await self._observation_repo.bulk_create(oecd_request_id=oecd_req.id, records=normalized)

            exec_time = elapsed_ms(start)
            await self._ingestion_repo.mark_success(run, exec_time)
            await self._session.commit()

            self._log_success(
                endpoint=endpoint,
                run_id=run.id,
                request_id=oecd_req.id,
                exec_time=exec_time,
                records=len(normalized),
                country=request.country,
                indicator_code=request.indicator_code,
            )

            return ObservationsResponse(
                request=request.model_dump(),
                metadata=self._meta(endpoint, exec_time, len(normalized), run.id, oecd_req.id),
                data=ObservationsData(
                    observations=[
                        ObservationItem(
                            country=obs["country"],
                            indicator_code=obs["indicator_code"],
                            indicator_name=obs.get("indicator_name"),
                            time_period=obs["time_period"],
                            value=obs.get("value"),
                            unit=obs.get("unit"),
                            frequency=obs.get("frequency"),
                            measure=obs.get("measure"),
                        )
                        for obs in normalized
                    ]
                ),
            )
        except Exception as e:
            await self._fail(run, endpoint, start, e)
            raise

    async def seed_catalog(self) -> IndicatorCatalogResponse:
        """Idempotent — upserts SEED_INDICATORS by indicator_code. Safe to
        call on every startup, not just after a fresh volume."""
        request = IndicatorCatalogRequest(indicators=[IndicatorCatalogItem(**item) for item in SEED_INDICATORS])
        return await self.upsert_indicator_catalog(request)

    async def upsert_indicator_catalog(self, request: IndicatorCatalogRequest) -> IndicatorCatalogResponse:
        records = [ind.model_dump() for ind in request.indicators]
        entities = await self._indicator_repo.upsert(records)
        await self._session.commit()
        return IndicatorCatalogResponse(
            indicators=[
                IndicatorCatalogItemResponse(
                    id=e.id,
                    indicator_code=e.indicator_code,
                    indicator_name=e.indicator_name,
                    description=e.description,
                    category=e.category,
                    expected_unit=e.expected_unit,
                    marketmind_dimension=e.marketmind_dimension,
                    dataflow_id=e.dataflow_id,
                    dataset_id=e.dataset_id,
                    is_active=e.is_active,
                    created_at=e.created_at,
                )
                for e in entities
            ],
            total=len(entities),
        )

    async def list_indicator_catalog(self) -> IndicatorCatalogResponse:
        entities = await self._indicator_repo.get_all()
        return IndicatorCatalogResponse(
            indicators=[
                IndicatorCatalogItemResponse(
                    id=e.id,
                    indicator_code=e.indicator_code,
                    indicator_name=e.indicator_name,
                    description=e.description,
                    category=e.category,
                    expected_unit=e.expected_unit,
                    marketmind_dimension=e.marketmind_dimension,
                    dataflow_id=e.dataflow_id,
                    dataset_id=e.dataset_id,
                    is_active=e.is_active,
                    created_at=e.created_at,
                )
                for e in entities
            ],
            total=len(entities),
        )

    async def collect_indicators(self, request: IndicatorCollectRequest) -> IndicatorCollectResponse:
        endpoint = OECDEndpoint.INDICATORS_COLLECT
        start = utc_now()
        run = await self._ingestion_repo.create(source="oecd", request_payload=request.model_dump())

        catalog = await self._indicator_repo.get_by_codes(request.indicator_codes)
        catalog_map = {c.indicator_code: c for c in catalog}

        missing = [code for code in request.indicator_codes if code not in catalog_map]
        if missing:
            exec_time = elapsed_ms(start)
            await self._ingestion_repo.mark_failed(
                run,
                f"Indicators not configured in catalog: {', '.join(missing)}. "
                "Use POST /indicators/catalog to configure them with dataflow_id first.",
                exec_time,
            )
            await self._session.commit()
            raise IndicatorNotConfiguredError(
                f"Indicators not configured in catalog: {', '.join(missing)}. "
                "Use POST /indicators/catalog to configure them with dataflow_id first."
            )

        not_configured = [code for code, ind in catalog_map.items() if not ind.dataflow_id]
        if not_configured:
            exec_time = elapsed_ms(start)
            await self._ingestion_repo.mark_failed(
                run,
                f"Indicators missing dataflow_id: {', '.join(not_configured)}. " "Update the catalog with dataflow_id.",
                exec_time,
            )
            await self._session.commit()
            raise IndicatorNotConfiguredError(
                f"Indicators missing dataflow_id in catalog: {', '.join(not_configured)}. "
                "Update the catalog with dataflow_id."
            )

        all_observations: list[dict[str, Any]] = []
        collected: list[str] = []
        failed: list[str] = []

        for code in request.indicator_codes:
            indicator = catalog_map[code]
            try:
                query_params: dict[str, str] = {}
                if request.start_period:
                    query_params["startPeriod"] = request.start_period
                if request.end_period:
                    query_params["endPeriod"] = request.end_period

                query_key = _build_series_key(indicator.dataflow_id, request.country, code)  # type: ignore[arg-type]
                data, url = await self._client.get_observations(
                    dataflow_id=indicator.dataflow_id,  # type: ignore[arg-type]
                    query_key=query_key,
                    query_params=query_params if query_params else None,
                )
                oecd_req = await self._oecd_request_repo.create(
                    ingestion_run_id=run.id,
                    endpoint=endpoint,
                    url=url,
                    dataset_id=indicator.dataset_id,
                    dataflow_id=indicator.dataflow_id,
                    country=request.country,
                    indicator_code=code,
                    start_period=request.start_period,
                    end_period=request.end_period,
                    query_params=query_params if query_params else None,
                )
                await self._raw_response_repo.create(
                    oecd_request_id=oecd_req.id,
                    endpoint=endpoint,
                    request_payload={"indicator_code": code, "country": request.country},
                    response_payload=data,
                )
                raw_obs = extract_observations(
                    data,
                    country=request.country,
                    indicator_code=code,
                    dataflow_id=indicator.dataflow_id,
                    dataset_id=indicator.dataset_id,
                )
                normalized = normalize_observations(raw_obs)
                await self._observation_repo.bulk_create(oecd_request_id=oecd_req.id, records=normalized)
                all_observations.extend(normalized)
                collected.append(code)
            except Exception as e:
                logger.error(f"Failed to collect indicator {code}: {e}")
                failed.append(code)

        exec_time = elapsed_ms(start)
        if failed and not collected:
            await self._ingestion_repo.mark_failed(run, f"All indicators failed: {', '.join(failed)}", exec_time)
        else:
            await self._ingestion_repo.mark_success(run, exec_time)
        await self._session.commit()

        first_req_id = run.id
        self._log_success(
            endpoint=endpoint,
            run_id=run.id,
            request_id=first_req_id,
            exec_time=exec_time,
            records=len(all_observations),
            country=request.country,
        )

        return IndicatorCollectResponse(
            request=request.model_dump(),
            metadata=self._meta(endpoint, exec_time, len(all_observations), run.id, first_req_id),
            data=IndicatorCollectData(
                observations=[
                    ObservationItem(
                        country=obs["country"],
                        indicator_code=obs["indicator_code"],
                        indicator_name=obs.get("indicator_name"),
                        time_period=obs["time_period"],
                        value=obs.get("value"),
                        unit=obs.get("unit"),
                        frequency=obs.get("frequency"),
                        measure=obs.get("measure"),
                    )
                    for obs in all_observations
                ],
                indicators_collected=collected,
                indicators_failed=failed,
            ),
        )

    async def get_oecd_request(self, request_id: Any) -> dict[str, Any] | None:
        req = await self._oecd_request_repo.get_by_id(request_id)
        if not req:
            return None
        result: dict[str, Any] = {
            "id": req.id,
            "ingestion_run_id": req.ingestion_run_id,
            "endpoint": req.endpoint,
            "url": req.url,
            "dataset_id": req.dataset_id,
            "dataflow_id": req.dataflow_id,
            "country": req.country,
            "indicator_code": req.indicator_code,
            "created_at": req.created_at,
            "data": [],
        }
        if req.endpoint == OECDEndpoint.DATAFLOWS:
            records = await self._dataflow_repo.get_by_oecd_request_id(request_id)
            result["data"] = [{"dataflow_id": r.dataflow_id, "name": r.name, "agency_id": r.agency_id} for r in records]
        elif req.endpoint == OECDEndpoint.DATASTRUCTURE:
            records = await self._datastructure_repo.get_by_oecd_request_id(request_id)
            result["data"] = [
                {
                    "dimension_id": r.dimension_id,
                    "dimension_name": r.dimension_name,
                    "code_id": r.code_id,
                    "code_name": r.code_name,
                }
                for r in records
            ]
        elif req.endpoint in (OECDEndpoint.OBSERVATIONS, OECDEndpoint.INDICATORS_COLLECT):
            records = await self._observation_repo.get_by_oecd_request_id(request_id)
            result["data"] = [
                {
                    "country": r.country,
                    "indicator_code": r.indicator_code,
                    "time_period": r.time_period,
                    "value": float(r.value) if r.value is not None else None,
                }
                for r in records
            ]
        return result

    async def get_ingestion_run(self, run_id: Any) -> dict[str, Any] | None:
        run = await self._ingestion_repo.get_by_id(run_id)
        if not run:
            return None
        return {
            "id": run.id,
            "source": run.source,
            "status": run.status,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "execution_time_ms": run.execution_time_ms,
            "request_payload": run.request_payload,
            "error_message": run.error_message,
            "created_at": run.created_at,
        }

    def _group_dimensions(self, parsed: list[dict[str, Any]]) -> list[DimensionItem]:
        dim_map: dict[str, DimensionItem] = {}
        for record in parsed:
            dim_id = record.get("dimension_id", "")
            if dim_id not in dim_map:
                dim_map[dim_id] = DimensionItem(
                    dimension_id=dim_id,
                    dimension_name=record.get("dimension_name"),
                    position=record.get("dimension_position"),
                    codes=[],
                )
            if record.get("code_id"):
                dim_map[dim_id].codes.append(CodeItem(code_id=record["code_id"], code_name=record.get("code_name")))
        return list(dim_map.values())

    def _meta(self, endpoint: str, exec_time: int, records: int, run_id: Any, request_id: Any) -> Metadata:
        return Metadata(
            endpoint=endpoint,
            execution_time_ms=exec_time,
            records=records,
            ingestion_run_id=run_id,
            oecd_request_id=request_id,
            status=IngestionStatus.SUCCESS,
            collected_at=utc_now(),
        )

    async def _fail(self, run: Any, endpoint: str, start: Any, error: Exception) -> None:
        exec_time = elapsed_ms(start)
        await self._ingestion_repo.mark_failed(run, str(error), exec_time)
        await self._session.commit()
        self._log_failure(endpoint, run.id, exec_time, str(error))

    def _log_success(
        self,
        endpoint: str,
        run_id: Any,
        request_id: Any,
        exec_time: int,
        records: int,
        country: str | None = None,
        indicator_code: str | None = None,
    ) -> None:
        logger.info(
            f"endpoint={endpoint} | country={country or ''} | indicator_code={indicator_code or ''} | "
            f"ingestion_run_id={run_id} | oecd_request_id={request_id} | "
            f"execution_time_ms={exec_time} | records={records} | status=success"
        )

    def _log_failure(self, endpoint: str, run_id: Any, exec_time: int, error: str) -> None:
        logger.error(
            f"endpoint={endpoint} | ingestion_run_id={run_id} | "
            f"execution_time_ms={exec_time} | status=failed | error={error}"
        )

    async def get_freshness(
        self,
        *,
        countries: list[str] | None = None,
        indicators: list[str] | None = None,
        stale_after_days: int = 30,
        only_stale: bool = False,
    ) -> FreshnessResponse:
        """What this service holds and when it last looked, per country and indicator.

        This is what lets a caller decide whether to ask for a collection,
        without keeping its own record of what was fetched when -- the
        bookkeeping that used to live outside this service and drift away from
        what the tables actually held.

        Naming BOTH a country and an indicator asks a closed question, so it
        gets a closed answer: every requested pair comes back, including pairs
        never fetched, marked stale with last_checked_at null. An empty list
        would be indistinguishable from "everything is fresh".
        """
        countries = [c.strip().upper() for c in countries if c.strip()] if countries else None
        indicators = [i.strip() for i in indicators if i.strip()] if indicators else None

        checks = await self._freshness_repo.last_checks(countries=countries, indicators=indicators)
        observed = await self._freshness_repo.observation_facts(countries=countries, indicators=indicators)

        if countries and indicators:
            pairs = [(country, indicator) for country in countries for indicator in indicators]
        else:
            pairs = sorted(set(checks) | set(observed))

        now = utc_now()
        cutoff = now - timedelta(days=stale_after_days)

        items: list[FreshnessItem] = []
        for country, indicator in pairs:
            # Normalizado antes de comparar: `utc_now()` é sem fuso e esta
            # coluna é `timestamp with time zone`, então a comparação crua é
            # TypeError — ver as_naive_utc.
            last_checked_at = as_naive_utc(checks.get((country, indicator)))
            facts = observed.get((country, indicator))
            stale = last_checked_at is None or last_checked_at < cutoff
            if only_stale and not stale:
                continue
            items.append(
                FreshnessItem(
                    country=country,
                    indicator_code=indicator,
                    last_checked_at=last_checked_at,
                    last_observation_at=facts.last_observation_at if facts else None,
                    latest_period=facts.latest_period if facts else None,
                    observation_count=facts.observation_count if facts else 0,
                    stale=stale,
                )
            )

        return FreshnessResponse(data=FreshnessData(as_of=now, stale_after_days=stale_after_days, items=items))

    async def get_series(
        self,
        *,
        country: str,
        measure: str | None = None,
        indicator_code: str | None = None,
        frequency: str | None = None,
        limit: int | None = None,
    ) -> SeriesResponse:
        """One series, one value per period, newest first.

        This is how a caller reads what was collected without opening this
        service's database. Reading another service's tables directly couples
        the reader to a schema it does not own, and a column rename here then
        breaks a calculation there, silently.

        Values come back as rows, never as a growth rate or an average. That
        arithmetic is versioned method and belongs to whoever owns the method.
        """
        rows = await self._observation_repo.series(
            country=country.strip().upper(),
            measure=measure.strip() if measure else None,
            indicator_code=indicator_code.strip() if indicator_code else None,
            frequency=frequency.strip().upper() if frequency else None,
            limit=limit,
        )
        return SeriesResponse(
            data=SeriesData(
                country=country.strip().upper(),
                measure=measure.strip() if measure else None,
                indicator_code=indicator_code.strip() if indicator_code else None,
                frequency=frequency.strip().upper() if frequency else None,
                points=[SeriesPoint(time_period=period, value=value) for period, value in rows],
            )
        )

    async def refresh_stale(self, request: RefreshStaleRequest) -> RefreshStaleResponse:
        """Collect again whatever has not been looked at in a while.

        This is the half of freshness that nobody has to ask for. The other half
        is the on-demand collection: something decides a country is needed now
        and asks. Between the two, data this service already holds stays current
        without anyone tracking it from outside -- and a second record of what
        was collected, kept elsewhere, drifts from the tables while the tables
        are the ones that can be wrong in silence.

        Bounded on purpose: a first run against a long-idle database finds every
        country stale at once, and the upstream API has its own patience.

        Each country is REPLAYED from its last successful request with the
        window moved to now, so whatever a caller once set up keeps working
        without this service learning which indicators that country uses.
        """
        freshness = await self.get_freshness(stale_after_days=request.stale_after_days, only_stale=True)

        stale_countries: list[str] = []
        for item in freshness.data.items:
            if item.country not in stale_countries:
                stale_countries.append(item.country)

        payloads = await self._ingestion_repo.last_successful_payload_by_country()
        end_year = utc_now().year
        start_year = end_year - request.years_back + 1

        outcomes: list[RefreshedCountry] = []
        refreshed = failed = skipped = 0

        for country in stale_countries[: request.limit]:
            payload = payloads.get(country)
            indicator_codes = (payload or {}).get("indicator_codes")
            if payload is None or not indicator_codes:
                skipped += 1
                outcomes.append(
                    RefreshedCountry(
                        country=country,
                        outcome="skipped",
                        detail="no successful collection to replay; collect it once on demand first",
                    )
                )
                continue

            try:
                await self.collect_indicators(
                    IndicatorCollectRequest(
                        country=payload.get("country", country),
                        start_period=str(start_year),
                        end_period=str(end_year),
                        indicator_codes=indicator_codes,
                    )
                )
                refreshed += 1
                outcomes.append(RefreshedCountry(country=country, outcome="refreshed"))
            except Exception as exc:  # noqa: BLE001 - one country failing must not end the pass
                failed += 1
                logger.warning(f"Scheduled refresh failed for country={country}: {exc}")
                outcomes.append(RefreshedCountry(country=country, outcome="failed", detail=str(exc)))

        return RefreshStaleResponse(
            data=RefreshStaleData(
                stale_after_days=request.stale_after_days,
                stale_countries=len(stale_countries),
                attempted=len(outcomes),
                refreshed=refreshed,
                failed=failed,
                skipped=skipped,
                countries=outcomes,
            )
        )
