from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException

from app.api.dependencies import get_oecd_service
from app.core.exceptions import (
    IndicatorNotConfiguredError,
    OECDClientError,
    OECDEmptyResponseError,
    OECDParsingError,
    OECDRateLimitError,
    OECDTimeoutError,
)
from app.schemas.requests import (
    DataflowsRequest,
    DatastructureRequest,
    IndicatorCatalogRequest,
    IndicatorCollectRequest,
    ObservationsRequest,
)
from app.schemas.responses import (
    DataflowsResponse,
    DatastructureResponse,
    ErrorResponse,
    FreshnessResponse,
    IndicatorCatalogResponse,
    IndicatorCollectResponse,
    IngestionRunResponse,
    ObservationsResponse,
    OECDRequestDetailResponse,
)
from app.services.oecd_service import OECDService

router = APIRouter()


@router.post(
    "/dataflows",
    response_model=DataflowsResponse,
    responses={502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
    summary="Discover OECD Dataflows",
    description="Fetches available OECD dataflows/datasets, normalizes and persists them.",
)
async def dataflows(
    request: DataflowsRequest,
    service: OECDService = Depends(get_oecd_service),
) -> DataflowsResponse:
    try:
        return await service.collect_dataflows(request)
    except OECDEmptyResponseError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OECDRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except OECDTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except OECDParsingError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except OECDClientError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post(
    "/datastructure",
    response_model=DatastructureResponse,
    responses={502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
    summary="Get Dataflow Structure",
    description="Fetches the structure (dimensions, codelists) of an OECD dataflow, normalizes and persists it.",
)
async def datastructure(
    request: DatastructureRequest,
    service: OECDService = Depends(get_oecd_service),
) -> DatastructureResponse:
    try:
        return await service.collect_datastructure(request)
    except OECDEmptyResponseError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OECDRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except OECDTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except OECDParsingError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except OECDClientError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post(
    "/observations",
    response_model=ObservationsResponse,
    responses={502: {"model": ErrorResponse}, 504: {"model": ErrorResponse}},
    summary="Collect OECD Observations",
    description="Fetches observations from an OECD dataflow, normalizes and persists them.",
)
async def observations(
    request: ObservationsRequest,
    service: OECDService = Depends(get_oecd_service),
) -> ObservationsResponse:
    try:
        return await service.collect_observations(request)
    except OECDEmptyResponseError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OECDRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except OECDTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except OECDParsingError as e:
        raise HTTPException(status_code=502, detail=str(e))
    except OECDClientError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post(
    "/indicators/catalog",
    response_model=IndicatorCatalogResponse,
    summary="Create/Update Indicator Catalog",
    description="Creates or updates the internal catalog of OECD indicators relevant to MarketMind.",
)
async def upsert_indicators(
    request: IndicatorCatalogRequest,
    service: OECDService = Depends(get_oecd_service),
) -> IndicatorCatalogResponse:
    return await service.upsert_indicator_catalog(request)


@router.get(
    "/freshness",
    response_model=FreshnessResponse,
    summary="What this service holds, and when it last looked",
    description=(
        "Reports, per country and indicator, when this service last ASKED the "
        "OECD -- not how recent the returned data is. The two are different, "
        "and a staleness rule written against the data's own period would treat "
        "every slowly-published series as permanently stale and re-fetch it "
        "every day.\n\n"
        "A pair that was checked and came back empty still reports a "
        "last_checked_at, so a country the source genuinely has no data for is "
        "not mistaken for one that was never tried.\n\n"
        "Naming both country and indicator asks a closed question and gets a "
        "closed answer: every requested pair is returned, including pairs never "
        "fetched (last_checked_at null, stale true)."
    ),
)
async def get_freshness(
    country: list[str] | None = Query(None, description="Country codes. Repeat the parameter for several."),
    indicator: list[str] | None = Query(None, description="Indicator codes. Repeat for several."),
    stale_after_days: int = Query(30, ge=1, le=3650, description="A check older than this counts as stale."),
    only_stale: bool = Query(False, description="Return only the pairs that need collecting."),
    service: OECDService = Depends(get_oecd_service),
) -> FreshnessResponse:
    return await service.get_freshness(
        countries=country,
        indicators=indicator,
        stale_after_days=stale_after_days,
        only_stale=only_stale,
    )


@router.get(
    "/indicators/catalog",
    response_model=IndicatorCatalogResponse,
    summary="List Indicator Catalog",
    description="Lists all indicators in the internal catalog.",
)
async def list_indicators(
    service: OECDService = Depends(get_oecd_service),
) -> IndicatorCatalogResponse:
    return await service.list_indicator_catalog()


@router.post(
    "/indicators/catalog/seed",
    response_model=IndicatorCatalogResponse,
    summary="Seed indicator catalog",
    description="Seeds the internal indicator catalog with the default MarketMind indicators (idempotent).",
)
async def seed_catalog(
    service: OECDService = Depends(get_oecd_service),
) -> IndicatorCatalogResponse:
    return await service.seed_catalog()


@router.post(
    "/indicators/collect",
    response_model=IndicatorCollectResponse,
    responses={
        400: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
    summary="Collect Indicators from Catalog",
    description=(
        "Collects OECD data for indicators defined in the internal catalog. "
        "Each indicator must have a dataflow_id configured."
    ),
)
async def collect_indicators(
    request: IndicatorCollectRequest,
    service: OECDService = Depends(get_oecd_service),
) -> IndicatorCollectResponse:
    try:
        return await service.collect_indicators(request)
    except IndicatorNotConfiguredError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except OECDEmptyResponseError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except OECDRateLimitError as e:
        raise HTTPException(status_code=429, detail=str(e))
    except OECDTimeoutError as e:
        raise HTTPException(status_code=504, detail=str(e))
    except OECDClientError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get(
    "/requests/{oecd_request_id}",
    response_model=OECDRequestDetailResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get OECD Request Details",
    description="Returns a stored OECD request with its associated normalized data.",
)
async def get_oecd_request(
    oecd_request_id: UUID,
    service: OECDService = Depends(get_oecd_service),
) -> OECDRequestDetailResponse:
    result = await service.get_oecd_request(oecd_request_id)
    if not result:
        raise HTTPException(status_code=404, detail="OECD request not found")
    return OECDRequestDetailResponse(**result)


@router.get(
    "/runs/{ingestion_run_id}",
    response_model=IngestionRunResponse,
    responses={404: {"model": ErrorResponse}},
    summary="Get Ingestion Run Details",
    description="Returns status and metadata of a specific ingestion run.",
)
async def get_ingestion_run(
    ingestion_run_id: UUID,
    service: OECDService = Depends(get_oecd_service),
) -> IngestionRunResponse:
    result = await service.get_ingestion_run(ingestion_run_id)
    if not result:
        raise HTTPException(status_code=404, detail="Ingestion run not found")
    return IngestionRunResponse(**result)
