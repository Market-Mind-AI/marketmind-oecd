import asyncio
from typing import Any

import httpx

from app.core.config import settings
from app.core.exceptions import OECDClientError, OECDEmptyResponseError, OECDRateLimitError, OECDTimeoutError
from app.core.logging import logger

ACCEPT_STRUCTURE = "application/vnd.sdmx.structure+json;charset=utf-8;version=1.0"
ACCEPT_DATA = "application/vnd.sdmx.data+json;charset=utf-8;version=1.0"


class OECDClient:
    def __init__(self) -> None:
        self._base_url = settings.oecd_base_url.rstrip("/")
        self._timeout = settings.default_timeout
        self._retries = settings.default_retries
        self._backoff = settings.default_backoff
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

    async def get_raw(self, url: str, params: dict[str, str] | None = None) -> dict[str, Any]:
        return await self._request(url, params or {})

    async def _request(
        self, url: str, params: dict[str, str], accept: str = ACCEPT_DATA
    ) -> dict[str, Any]:
        headers = {"Accept": accept, "User-Agent": self._user_agent}
        last_error: Exception | None = None
        for attempt in range(1, self._retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
                    response = await client.get(url, params=params)

                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", self._backoff * attempt))
                    logger.warning(f"OECD rate limit hit (429). Retry-After={retry_after}s | attempt={attempt}")
                    if attempt < self._retries:
                        await asyncio.sleep(retry_after)
                        continue
                    raise OECDRateLimitError(f"Rate limit exceeded after {self._retries} attempts")

                if response.status_code == 404:
                    raise OECDEmptyResponseError(f"No data found at {url}")

                if response.status_code >= 400:
                    raise OECDClientError(
                        f"OECD API error: status={response.status_code} url={url} body={response.text[:500]}"
                    )

                data = response.json()
                if not data:
                    raise OECDEmptyResponseError(f"Empty response from {url}")
                return data  # type: ignore[no-any-return]

            except httpx.TimeoutException as e:
                last_error = OECDTimeoutError(f"Timeout requesting {url}: {e}")
                logger.warning(f"Timeout on attempt {attempt}/{self._retries} for {url}")
                if attempt < self._retries:
                    await asyncio.sleep(self._backoff * attempt)
                    continue
            except (OECDRateLimitError, OECDEmptyResponseError, OECDClientError):
                raise
            except httpx.HTTPError as e:
                last_error = OECDClientError(f"HTTP error requesting {url}: {e}")
                logger.warning(f"HTTP error on attempt {attempt}/{self._retries} for {url}: {e}")
                if attempt < self._retries:
                    await asyncio.sleep(self._backoff * attempt)
                    continue

        raise last_error or OECDClientError(f"Failed after {self._retries} attempts for {url}")
