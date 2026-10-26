from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api.dependencies import get_oecd_service
from app.core.exceptions import OECDEmptyResponseError, OECDTimeoutError
from app.main import app
from app.schemas.responses import (
    DataflowItem,
    DataflowsData,
    DataflowsResponse,
    Metadata,
)
from app.services.oecd_service import OECDService


def _create_mock_service() -> AsyncMock:
    return AsyncMock(spec=OECDService)


class TestDataflowsEndpoint:
    def test_dataflows_success(self) -> None:
        mock_service = _create_mock_service()
        run_id = uuid4()
        req_id = uuid4()
        mock_service.collect_dataflows = AsyncMock(
            return_value=DataflowsResponse(
                request={"agency_id": "OECD", "detail": "allstubs"},
                metadata=Metadata(
                    endpoint="dataflows",
                    execution_time_ms=500,
                    records=1,
                    ingestion_run_id=run_id,
                    oecd_request_id=req_id,
                    status="success",
                    collected_at=datetime(2026, 6, 29, 10, 0, 0),
                ),
                data=DataflowsData(
                    dataflows=[
                        DataflowItem(
                            agency_id="OECD",
                            dataflow_id="DF_CCI",
                            name="Consumer confidence",
                            version="1.0",
                        )
                    ]
                ),
            )
        )

        async def override():
            yield mock_service

        app.dependency_overrides[get_oecd_service] = override
        with TestClient(app) as client:
            response = client.post("/dataflows", json={"agency_id": "OECD", "detail": "allstubs"})
        app.dependency_overrides.clear()

        assert response.status_code == 200

    def test_dataflows_timeout(self) -> None:
        mock_service = _create_mock_service()
        mock_service.collect_dataflows = AsyncMock(side_effect=OECDTimeoutError("timeout"))

        async def override():
            yield mock_service

        app.dependency_overrides[get_oecd_service] = override
        with TestClient(app) as client:
            response = client.post("/dataflows", json={"agency_id": "OECD"})
        app.dependency_overrides.clear()

        # Timeout esgotado é fonte fora do ar: 503 em todos os coletores.
        assert response.status_code == 503

    def test_dataflows_empty(self) -> None:
        mock_service = _create_mock_service()
        mock_service.collect_dataflows = AsyncMock(side_effect=OECDEmptyResponseError("no data"))

        async def override():
            yield mock_service

        app.dependency_overrides[get_oecd_service] = override
        with TestClient(app) as client:
            response = client.post("/dataflows", json={"agency_id": "OECD"})
        app.dependency_overrides.clear()

        assert response.status_code == 404


class TestObservationsEndpoint:
    def test_observations_validation_error(self) -> None:
        with TestClient(app) as client:
            response = client.post(
                "/observations",
                json={
                    "dataflow_id": "DF_CCI",
                    "country": "es",
                    "indicator_code": "CCI",
                },
            )
        assert response.status_code == 422

    def test_observations_invalid_period(self) -> None:
        with TestClient(app) as client:
            response = client.post(
                "/observations",
                json={
                    "dataflow_id": "DF_CCI",
                    "country": "ES",
                    "indicator_code": "CCI",
                    "start_period": "2026",
                    "end_period": "2020",
                },
            )
        assert response.status_code == 422


class TestIngestionRunEndpoint:
    def test_run_not_found(self) -> None:
        mock_service = _create_mock_service()
        mock_service.get_ingestion_run = AsyncMock(return_value=None)

        async def override():
            yield mock_service

        app.dependency_overrides[get_oecd_service] = override
        with TestClient(app) as client:
            response = client.get(f"/runs/{uuid4()}")
        app.dependency_overrides.clear()

        assert response.status_code == 404


class TestOECDRequestEndpoint:
    def test_request_not_found(self) -> None:
        mock_service = _create_mock_service()
        mock_service.get_oecd_request = AsyncMock(return_value=None)

        async def override():
            yield mock_service

        app.dependency_overrides[get_oecd_service] = override
        with TestClient(app) as client:
            response = client.get(f"/requests/{uuid4()}")
        app.dependency_overrides.clear()

        assert response.status_code == 404
