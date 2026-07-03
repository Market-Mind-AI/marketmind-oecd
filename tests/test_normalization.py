from decimal import Decimal

from app.utils.normalization import normalize_observations, normalize_value


class TestNormalizeValue:
    def test_none(self) -> None:
        assert normalize_value(None) is None

    def test_int(self) -> None:
        assert normalize_value(42) == 42

    def test_float(self) -> None:
        assert normalize_value(98.4) == 98.4

    def test_nan_float(self) -> None:
        assert normalize_value(float("nan")) is None

    def test_inf_float(self) -> None:
        assert normalize_value(float("inf")) is None

    def test_string_number(self) -> None:
        assert normalize_value("98.4") == 98.4

    def test_empty_string(self) -> None:
        assert normalize_value("") is None

    def test_nan_string(self) -> None:
        assert normalize_value("NaN") is None

    def test_na_string(self) -> None:
        assert normalize_value("N/A") is None

    def test_decimal(self) -> None:
        assert normalize_value(Decimal("98.4")) == 98.4

    def test_invalid_string(self) -> None:
        assert normalize_value("abc") is None


class TestNormalizeObservations:
    def test_normalizes_list(self) -> None:
        raw = [
            {
                "country": "ES",
                "indicator_code": "CCI",
                "time_period": "2026-01",
                "value": 98.4,
                "unit": "index",
                "frequency": "M",
            },
            {
                "country": "ES",
                "indicator_code": "CCI",
                "time_period": "2026-02",
                "value": None,
            },
        ]
        result = normalize_observations(raw)
        assert len(result) == 2
        assert result[0]["value"] == 98.4
        assert result[0]["country"] == "ES"
        assert result[1]["value"] is None

    def test_empty_list(self) -> None:
        result = normalize_observations([])
        assert result == []

    def test_nan_value_cleaned(self) -> None:
        raw = [
            {
                "country": "ES",
                "indicator_code": "CCI",
                "time_period": "2026-01",
                "value": float("nan"),
            }
        ]
        result = normalize_observations(raw)
        assert result[0]["value"] is None
