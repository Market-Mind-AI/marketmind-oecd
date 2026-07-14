from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.clients.oecd_client import OECDClient
from app.core.exceptions import (
    OECDClientError,
    OECDEmptyResponseError,
    OECDRateLimitError,
    OECDTimeoutError,
    OECDTransientError,
)


@pytest.fixture
def oecd_client() -> OECDClient:
    return OECDClient()


class TestOECDClientGetDataflows:
    @pytest.mark.asyncio
    async def test_success(self, oecd_client: OECDClient) -> None:
        mock_response = httpx.Response(
            status_code=200,
            json={"data": {"dataflows": []}},
            request=httpx.Request("GET", "https://test.com"),
        )
        with patch("app.clients.oecd_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            data, url = await oecd_client.get_dataflows()
            assert "data" in data
            assert "dataflows" in data["data"]

    @pytest.mark.asyncio
    async def test_timeout(self, oecd_client: OECDClient) -> None:
        oecd_client._retries = 1
        with patch("app.clients.oecd_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with pytest.raises(OECDTimeoutError):
                await oecd_client.get_dataflows()

    @pytest.mark.asyncio
    async def test_rate_limit(self, oecd_client: OECDClient) -> None:
        oecd_client._retries = 1
        mock_response = httpx.Response(
            status_code=429,
            headers={"Retry-After": "1"},
            request=httpx.Request("GET", "https://test.com"),
        )
        with patch("app.clients.oecd_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with pytest.raises(OECDRateLimitError):
                await oecd_client.get_dataflows()

    @pytest.mark.asyncio
    async def test_empty_response(self, oecd_client: OECDClient) -> None:
        mock_response = httpx.Response(
            status_code=404,
            request=httpx.Request("GET", "https://test.com"),
        )
        with patch("app.clients.oecd_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with pytest.raises(OECDEmptyResponseError):
                await oecd_client.get_dataflows()

    @pytest.mark.asyncio
    async def test_server_error(self, oecd_client: OECDClient) -> None:
        oecd_client._retries = 1
        oecd_client._backoff = 0
        mock_response = httpx.Response(
            status_code=500,
            text="Internal Server Error",
            request=httpx.Request("GET", "https://test.com"),
        )
        with patch("app.clients.oecd_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with pytest.raises(OECDClientError):
                await oecd_client.get_dataflows()

    @pytest.mark.asyncio
    async def test_server_error_raises_transient(self, oecd_client: OECDClient) -> None:
        oecd_client._retries = 1
        oecd_client._backoff = 0
        mock_response = httpx.Response(
            status_code=503,
            text="Service Unavailable",
            request=httpx.Request("GET", "https://test.com"),
        )
        with patch("app.clients.oecd_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_response)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            with pytest.raises(OECDTransientError):
                await oecd_client.get_dataflows()


class TestOECDClientRetry:
    @pytest.mark.asyncio
    async def test_retry_on_timeout(self, oecd_client: OECDClient) -> None:
        oecd_client._retries = 2
        oecd_client._backoff = 0

        mock_success = httpx.Response(
            status_code=200,
            json={"data": {"dataflows": []}},
            request=httpx.Request("GET", "https://test.com"),
        )

        with patch("app.clients.oecd_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(
                side_effect=[httpx.TimeoutException("timeout"), mock_success]
            )
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            data, url = await oecd_client.get_dataflows()
            assert "data" in data
            assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_retry_on_server_error(self, oecd_client: OECDClient) -> None:
        oecd_client._retries = 2
        oecd_client._backoff = 0

        mock_error = httpx.Response(
            status_code=503,
            text="Service Unavailable",
            request=httpx.Request("GET", "https://test.com"),
        )
        mock_success = httpx.Response(
            status_code=200,
            json={"data": {"dataflows": []}},
            request=httpx.Request("GET", "https://test.com"),
        )

        with patch("app.clients.oecd_client.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(side_effect=[mock_error, mock_success])
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=None)
            mock_client_cls.return_value = mock_client

            data, url = await oecd_client.get_dataflows()
            assert "data" in data
            assert mock_client.get.call_count == 2
