from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient

from app.db.session import get_session
from app.main import app


class TestHealthEndpoint:
    def test_health_ok(self) -> None:
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session
        with TestClient(app) as client:
            response = client.get("/health")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "connected"
        assert data["app_name"] == "marketmind-oecd"

    def test_health_db_disconnected(self) -> None:
        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(side_effect=Exception("connection failed"))

        async def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session
        with TestClient(app) as client:
            response = client.get("/health")
        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["database"] == "disconnected"


class TestVersionEndpoint:
    def test_version(self) -> None:
        with TestClient(app) as client:
            response = client.get("/version")

        assert response.status_code == 200
        data = response.json()
        assert data["app_name"] == "marketmind-oecd"
        assert "version" in data


def test_healthz_answers_without_touching_the_database() -> None:
    """What a liveness probe asks: can THIS process still answer. It must not
    depend on Postgres — a probe that does restarts the pod because the database
    is slow, which fixes nothing and throws away whatever was in flight.

    No database fixture here, deliberately: if this endpoint ever starts needing
    one, this test fails.
    """
    from fastapi.testclient import TestClient

    from app.main import app

    response = TestClient(app).get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
