import asyncio
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import (
    OECDClientError,
    OECDEmptyResponseError,
    OECDRateLimitError,
    OECDTimeoutError,
    OECDTransientError,
)
from app.core.logging import logger
from app.utils.retry import backoff_seconds, is_retryable_status

ACCEPT_STRUCTURE = "application/vnd.sdmx.structure+json;charset=utf-8;version=1.0"
ACCEPT_DATA = "application/vnd.sdmx.data+json;charset=utf-8;version=1.0"


class OECDClient:
    def __init__(self) -> None:
        self._base_url = settings.oecd_base_url.rstrip("/")
        self._timeout = settings.default_timeout
        self._retries = settings.default_retries
        self._user_agent = f"{settings.app_name}/{settings.app_version}"

    async def get_dataflows(self, agency_id: str = "OECD", detail: str = "allstubs") -> tuple[dict[str, Any], str]:
        url = f"{self._base_url}/dataflow/{agency_id}"
        params = {"detail": detail}
        data = await self._request(url, params, accept=ACCEPT_STRUCTURE)
        return data, url

    async def get_datastructure(
        self,
        agency_id: str = "OECD",
        dataflow_id: str = "",
        structure_id: str | None = None,
    ) -> tuple[dict[str, Any], str]:
        if structure_id:
            url = f"{self._base_url}/datastructure/{agency_id}/{structure_id}"
        else:
            url = f"{self._base_url}/dataflow/{agency_id}/{dataflow_id}"
        params = {"detail": "full", "references": "all"}
        data = await self._request(url, params, accept=ACCEPT_STRUCTURE)
        return data, url

    async def get_observations(
        self,
        dataflow_id: str,
        query_key: str | None = None,
        query_params: dict[str, str] | None = None,
    ) -> tuple[dict[str, Any], str]:
        key = query_key or "all"
        url = f"{self._base_url}/data/{dataflow_id}/{key}"
        params = query_params or {}
        data = await self._request(url, params, accept=ACCEPT_DATA)
        return data, url

    async def _request(self, url: str, params: dict[str, str], accept: str = ACCEPT_DATA) -> dict[str, Any]:
        """Uma chamada à API, insistindo enquanto a falha for passageira.

        Quando e quanto insistir é a política comum aos quatro coletores, em
        app/utils/retry.py. Esgotadas as tentativas, a falha passageira sobe
        como OECDTransientError (503). Um 404 é a fonte dizendo que não tem o
        dado e sobe como OECDEmptyResponseError, sem repetir; os outros 4xx
        sobem como OECDClientError, também sem repetir.
        """
        headers = {"Accept": accept, "User-Agent": self._user_agent}
        last_error: OECDTransientError | None = None
        for attempt in range(1, self._retries + 1):
            retry_after: str | None = None
            try:
                async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
                    response = await client.get(url, params=params)
            except httpx.TimeoutException as e:
                last_error = OECDTimeoutError(f"Timeout requesting {url}: {e}")
            except httpx.HTTPError as e:
                # Rede: DNS, conexão recusada ou derrubada. É a fonte (ou o
                # caminho até ela) fora do ar, e esperar resolve.
                last_error = OECDTransientError(f"Network error requesting {url}: {e}")
            else:
                status = response.status_code
                if is_retryable_status(status):
                    retry_after = response.headers.get("Retry-After")
                    if status == 429:
                        last_error = OECDRateLimitError(f"OECD rate limit hit (429) for {url}")
                    else:
                        last_error = OECDTransientError(f"OECD server error: status={status} url={url}")
                elif status == 404:
                    raise OECDEmptyResponseError(f"No data found at {url}")
                elif status >= 400:
                    raise OECDClientError(f"OECD API error: status={status} url={url} body={response.text[:500]}")
                else:
                    data = response.json()
                    if not data:
                        raise OECDEmptyResponseError(f"Empty response from {url}")
                    return data  # type: ignore[no-any-return]

            logger.warning(f"OECD attempt {attempt}/{self._retries} failed: {last_error}")
            if attempt < self._retries:
                await asyncio.sleep(backoff_seconds(attempt, retry_after))

        raise last_error or OECDTransientError(f"Failed after {self._retries} attempts for {url}")
