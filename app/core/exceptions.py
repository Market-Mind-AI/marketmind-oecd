class OECDClientError(Exception):
    pass


class OECDTimeoutError(OECDClientError):
    pass


class OECDRateLimitError(OECDClientError):
    pass


class OECDTransientError(OECDClientError):
    """A transient upstream failure (HTTP 5xx) worth retrying — the OECD SDMX
    API returns intermittent 500/502/503/504 under load. Distinct from a plain
    OECDClientError (non-retryable 4xx) so the request loop backs off and
    retries instead of failing the whole collection on a blip, which downstream
    would abort a MarketMind analysis via its completeness gate."""

    pass


class OECDEmptyResponseError(Exception):
    pass


class OECDParsingError(Exception):
    pass


class IndicatorNotConfiguredError(Exception):
    pass
