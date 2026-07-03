import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_oecd_service
from app.db.session import get_session
from app.main import app
from app.services.oecd_service import OECDService


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def mock_oecd_service(mock_session: AsyncMock) -> OECDService:
    return OECDService(mock_session)


@pytest.fixture
def client(mock_session: AsyncMock) -> TestClient:
    async def override_session() -> AsyncGenerator[AsyncSession, None]:
        yield mock_session  # type: ignore[misc]

    async def override_service() -> AsyncGenerator[OECDService, None]:
        yield OECDService(mock_session)  # type: ignore[arg-type]

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_oecd_service] = override_service

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


SAMPLE_DATAFLOWS_RESPONSE = {
    "data": {
        "dataflows": [
            {
                "id": "DF_CCI",
                "agencyID": "OECD",
                "name": {"en": "Consumer confidence indicator"},
                "description": {"en": "Consumer confidence"},
                "version": "1.0",
                "isFinal": True,
            },
            {
                "id": "DF_KEI",
                "agencyID": "OECD",
                "name": {"en": "Key Economic Indicators"},
                "description": None,
                "version": "2.0",
                "isFinal": False,
            },
        ]
    }
}

SAMPLE_DATASTRUCTURE_RESPONSE = {
    "data": {
        "dataStructures": [
            {
                "id": "DSD_CCI",
                "dataStructureComponents": {
                    "dimensionList": {
                        "dimensions": [
                            {
                                "id": "REF_AREA",
                                "name": {"en": "Reference area"},
                                "position": 1,
                                "localRepresentation": {},
                            },
                            {
                                "id": "INDICATOR",
                                "name": {"en": "Indicator"},
                                "position": 2,
                                "localRepresentation": {},
                            },
                        ]
                    }
                },
            }
        ]
    }
}

SAMPLE_OBSERVATIONS_RESPONSE = {
    "data": {
        "dataSets": [
            {
                "series": {
                    "0:0": {
                        "observations": {
                            "0": [98.4],
                            "1": [99.1],
                            "2": [None],
                        }
                    }
                }
            }
        ],
        "structure": {
            "dimensions": {
                "series": [
                    {
                        "id": "REF_AREA",
                        "name": {"en": "Reference area"},
                        "values": [{"id": "ES", "name": "Spain"}],
                        "keyPosition": 0,
                    },
                    {
                        "id": "INDICATOR",
                        "name": {"en": "Indicator"},
                        "values": [{"id": "CCI", "name": "Consumer Confidence"}],
                        "keyPosition": 1,
                    },
                ],
                "observation": [
                    {
                        "id": "TIME_PERIOD",
                        "name": {"en": "Time period"},
                        "values": [
                            {"id": "2026-01", "name": "January 2026"},
                            {"id": "2026-02", "name": "February 2026"},
                            {"id": "2026-03", "name": "March 2026"},
                        ],
                    }
                ],
            },
            "attributes": {"observation": []},
        },
    }
}
