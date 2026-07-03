import pytest
from pydantic import ValidationError

from app.schemas.requests import (
    DataflowsRequest,
    DatastructureRequest,
    IndicatorCatalogItem,
    IndicatorCatalogRequest,
    IndicatorCollectRequest,
    ObservationsRequest,
)


class TestDataflowsRequest:
    def test_defaults(self) -> None:
        req = DataflowsRequest()
        assert req.agency_id == "OECD"
        assert req.detail == "allstubs"

    def test_custom_values(self) -> None:
        req = DataflowsRequest(agency_id="IMF", detail="full")
        assert req.agency_id == "IMF"
        assert req.detail == "full"


class TestDatastructureRequest:
    def test_valid(self) -> None:
        req = DatastructureRequest(dataflow_id="DF_CCI")
        assert req.dataflow_id == "DF_CCI"
        assert req.agency_id == "OECD"

    def test_empty_dataflow_id(self) -> None:
        with pytest.raises(ValidationError):
            DatastructureRequest(dataflow_id="")


class TestObservationsRequest:
    def test_valid(self) -> None:
        req = ObservationsRequest(
            dataflow_id="DF_CCI",
            country="ES",
            indicator_code="CCI",
            start_period="2020",
            end_period="2026",
        )
        assert req.country == "ES"
        assert req.indicator_code == "CCI"

    def test_invalid_country_lowercase(self) -> None:
        with pytest.raises(ValidationError):
            ObservationsRequest(
                dataflow_id="DF_CCI",
                country="es",
                indicator_code="CCI",
            )

    def test_invalid_country_too_long(self) -> None:
        with pytest.raises(ValidationError):
            ObservationsRequest(
                dataflow_id="DF_CCI",
                country="ESXX",
                indicator_code="CCI",
            )

    def test_iso3_country(self) -> None:
        req = ObservationsRequest(
            dataflow_id="DF_CCI",
            country="ESP",
            indicator_code="CCI",
        )
        assert req.country == "ESP"

    def test_invalid_periods(self) -> None:
        with pytest.raises(ValidationError):
            ObservationsRequest(
                dataflow_id="DF_CCI",
                country="ES",
                indicator_code="CCI",
                start_period="2026",
                end_period="2020",
            )


class TestIndicatorCatalogRequest:
    def test_valid(self) -> None:
        req = IndicatorCatalogRequest(
            indicators=[
                IndicatorCatalogItem(
                    indicator_code="CCI",
                    indicator_name="Consumer Confidence",
                    category="consumer_confidence",
                )
            ]
        )
        assert len(req.indicators) == 1

    def test_empty_indicators(self) -> None:
        with pytest.raises(ValidationError):
            IndicatorCatalogRequest(indicators=[])


class TestIndicatorCollectRequest:
    def test_valid(self) -> None:
        req = IndicatorCollectRequest(
            country="ES",
            indicator_codes=["CCI"],
        )
        assert req.country == "ES"

    def test_invalid_periods(self) -> None:
        with pytest.raises(ValidationError):
            IndicatorCollectRequest(
                country="ES",
                start_period="2026",
                end_period="2020",
                indicator_codes=["CCI"],
            )

    def test_empty_indicator_codes(self) -> None:
        with pytest.raises(ValidationError):
            IndicatorCollectRequest(
                country="ES",
                indicator_codes=[],
            )
