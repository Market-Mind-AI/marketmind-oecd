from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class Metadata(BaseModel):
    provider: str = "OECD"
    standard: str = "SDMX"
    endpoint: str
    execution_time_ms: int
    records: int
    stored: bool = True
    ingestion_run_id: UUID
    oecd_request_id: UUID
    status: str
    collected_at: datetime


class HealthResponse(BaseModel):
    status: str
    database: str
    app_name: str
    environment: str


class VersionResponse(BaseModel):
    app_name: str
    version: str
    environment: str


class DataflowItem(BaseModel):
    agency_id: str | None = None
    dataflow_id: str
    name: str | None = None
    description: str | None = None
    version: str | None = None


class DataflowsData(BaseModel):
    dataflows: list[DataflowItem]


class DataflowsResponse(BaseModel):
    request: dict
    metadata: Metadata
    data: DataflowsData

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "request": {"agency_id": "OECD", "detail": "allstubs"},
                    "metadata": {
                        "provider": "OECD",
                        "standard": "SDMX",
                        "endpoint": "dataflows",
                        "execution_time_ms": 512,
                        "records": 100,
                        "stored": True,
                        "ingestion_run_id": "550e8400-e29b-41d4-a716-446655440000",
                        "oecd_request_id": "550e8400-e29b-41d4-a716-446655440001",
                        "status": "success",
                        "collected_at": "2026-06-29T10:00:00Z",
                    },
                    "data": {
                        "dataflows": [
                            {
                                "agency_id": "OECD",
                                "dataflow_id": "DF_CCI",
                                "name": "Consumer confidence indicator",
                                "description": "...",
                                "version": "1.0",
                            }
                        ]
                    },
                }
            ]
        }
    }


class CodeItem(BaseModel):
    code_id: str
    code_name: str | None = None


class DimensionItem(BaseModel):
    dimension_id: str
    dimension_name: str | None = None
    position: int | None = None
    codes: list[CodeItem] = Field(default_factory=list)


class DatastructureData(BaseModel):
    dimensions: list[DimensionItem]


class DatastructureResponse(BaseModel):
    request: dict
    metadata: Metadata
    data: DatastructureData

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "request": {"agency_id": "OECD", "dataflow_id": "DF_CCI"},
                    "metadata": {
                        "provider": "OECD",
                        "standard": "SDMX",
                        "endpoint": "datastructure",
                        "execution_time_ms": 300,
                        "records": 5,
                        "stored": True,
                        "ingestion_run_id": "550e8400-e29b-41d4-a716-446655440000",
                        "oecd_request_id": "550e8400-e29b-41d4-a716-446655440001",
                        "status": "success",
                        "collected_at": "2026-06-29T10:00:00Z",
                    },
                    "data": {
                        "dimensions": [
                            {
                                "dimension_id": "REF_AREA",
                                "dimension_name": "Reference area",
                                "position": 1,
                                "codes": [{"code_id": "ES", "code_name": "Spain"}],
                            }
                        ]
                    },
                }
            ]
        }
    }


class ObservationItem(BaseModel):
    country: str
    indicator_code: str
    indicator_name: str | None = None
    time_period: str
    value: float | Decimal | None = None
    unit: str | None = None
    frequency: str | None = None
    measure: str | None = None


class ObservationsData(BaseModel):
    observations: list[ObservationItem]


class ObservationsResponse(BaseModel):
    request: dict
    metadata: Metadata
    data: ObservationsData

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "request": {
                        "dataflow_id": "DF_CCI",
                        "country": "ES",
                        "indicator_code": "CCI",
                        "start_period": "2020",
                        "end_period": "2026",
                    },
                    "metadata": {
                        "provider": "OECD",
                        "standard": "SDMX",
                        "endpoint": "observations",
                        "execution_time_ms": 1200,
                        "records": 72,
                        "stored": True,
                        "ingestion_run_id": "550e8400-e29b-41d4-a716-446655440000",
                        "oecd_request_id": "550e8400-e29b-41d4-a716-446655440001",
                        "status": "success",
                        "collected_at": "2026-06-29T10:00:00Z",
                    },
                    "data": {
                        "observations": [
                            {
                                "country": "ES",
                                "indicator_code": "CCI",
                                "indicator_name": "Consumer Confidence Indicator",
                                "time_period": "2026-01",
                                "value": 98.4,
                                "unit": "index",
                                "frequency": "M",
                            }
                        ]
                    },
                }
            ]
        }
    }


class IndicatorCatalogItemResponse(BaseModel):
    id: UUID
    indicator_code: str
    indicator_name: str
    description: str | None = None
    category: str
    expected_unit: str | None = None
    marketmind_dimension: str | None = None
    dataflow_id: str | None = None
    dataset_id: str | None = None
    is_active: bool
    created_at: datetime


class IndicatorCatalogResponse(BaseModel):
    indicators: list[IndicatorCatalogItemResponse]
    total: int


class IndicatorCollectData(BaseModel):
    observations: list[ObservationItem]
    indicators_collected: list[str]
    indicators_failed: list[str] = Field(default_factory=list)


class IndicatorCollectResponse(BaseModel):
    request: dict
    metadata: Metadata
    data: IndicatorCollectData


class OECDRequestDetailResponse(BaseModel):
    id: UUID
    ingestion_run_id: UUID
    endpoint: str
    url: str
    dataset_id: str | None = None
    dataflow_id: str | None = None
    country: str | None = None
    indicator_code: str | None = None
    created_at: datetime
    data: list[dict[str, Any]] = Field(default_factory=list)


class IngestionRunResponse(BaseModel):
    id: UUID
    source: str
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    execution_time_ms: int | None = None
    request_payload: dict
    error_message: str | None = None
    created_at: datetime


class ErrorResponse(BaseModel):
    detail: str
    ingestion_run_id: UUID | None = None


class FreshnessItem(BaseModel):
    country: str
    indicator_code: str
    # When we last ASKED the OECD, not how recent the data is. These are
    # different questions and only the first one says whether to fetch again: a
    # rule written against the data's own period would treat every series that
    # publishes slowly as permanently stale and re-fetch it every day.
    last_checked_at: datetime | None = None
    last_observation_at: datetime | None = None
    latest_period: str | None = None
    observation_count: int = 0
    stale: bool


class FreshnessData(BaseModel):
    as_of: datetime
    stale_after_days: int
    items: list[FreshnessItem]


class FreshnessResponse(BaseModel):
    data: FreshnessData
