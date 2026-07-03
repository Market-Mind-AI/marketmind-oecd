from app.services.oecd_service import _build_series_key


class TestBuildSeriesKey:
    def test_scopes_ref_area_and_measure_for_known_dataflow(self) -> None:
        key = _build_series_key("DSD_PRICES@DF_PRICES_ALL", "ESP", "CPI")
        assert key == "ESP...CPI...."
        assert key.count(".") == 7

    def test_returns_none_for_unknown_dataflow(self) -> None:
        assert _build_series_key("DSD_UNKNOWN@DF_UNKNOWN", "ESP", "CPI") is None
