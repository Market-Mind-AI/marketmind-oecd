from enum import StrEnum


class IngestionStatus(StrEnum):
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class OECDEndpoint(StrEnum):
    DATAFLOWS = "dataflows"
    DATASTRUCTURE = "datastructure"
    OBSERVATIONS = "observations"
    INDICATORS_CATALOG = "indicators_catalog"
    INDICATORS_COLLECT = "indicators_collect"
