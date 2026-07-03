class OECDClientError(Exception):
    pass


class OECDTimeoutError(OECDClientError):
    pass


class OECDRateLimitError(OECDClientError):
    pass


class OECDEmptyResponseError(Exception):
    pass


class OECDParsingError(Exception):
    pass


class IngestionError(Exception):
    pass


class IndicatorNotConfiguredError(Exception):
    pass
