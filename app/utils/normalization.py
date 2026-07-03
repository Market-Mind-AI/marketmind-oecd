import math
from decimal import Decimal, InvalidOperation
from typing import Any


def normalize_value(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value or value.lower() in ("nan", "n/a", "na", "none", "null", ""):
            return None
        try:
            return float(value)
        except ValueError:
            return None
    if isinstance(value, (int, float)):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, Decimal):
        try:
            f = float(value)
            if math.isnan(f) or math.isinf(f):
                return None
            return f
        except (InvalidOperation, ValueError):
            return None
    return None


def normalize_observations(raw_observations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for obs in raw_observations:
        value = normalize_value(obs.get("value"))
        normalized.append(
            {
                "dataset_id": obs.get("dataset_id"),
                "dataflow_id": obs.get("dataflow_id"),
                "country": obs.get("country", ""),
                "indicator_code": obs.get("indicator_code", ""),
                "indicator_name": obs.get("indicator_name"),
                "measure": obs.get("measure"),
                "unit": obs.get("unit"),
                "frequency": obs.get("frequency"),
                "time_period": obs.get("time_period", ""),
                "value": value,
                "normalized_value": None,
                "attributes": obs.get("attributes"),
            }
        )
    return normalized


def clean_empty_strings(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None
