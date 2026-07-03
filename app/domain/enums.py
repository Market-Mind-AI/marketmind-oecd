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


class IndicatorCategory(StrEnum):
    CONSUMER_CONFIDENCE = "consumer_confidence"
    DISPOSABLE_INCOME = "disposable_income"
    HOUSEHOLD_CONSUMPTION = "household_consumption"
    INFLATION = "inflation"
    UNEMPLOYMENT = "unemployment"
    RETAIL_SALES = "retail_sales"


class MarketMindDimension(StrEnum):
    ECONOMIC_READINESS = "economic_readiness"
    PURCHASING_POWER = "purchasing_power"
    CONSUMPTION_CAPACITY = "consumption_capacity"
    MACROECONOMIC_RISK = "macroeconomic_risk"
