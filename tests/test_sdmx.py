
from app.utils.sdmx import extract_dataflows, extract_dimensions, extract_observations
from tests.conftest import (
    SAMPLE_DATAFLOWS_RESPONSE,
    SAMPLE_DATASTRUCTURE_RESPONSE,
    SAMPLE_OBSERVATIONS_RESPONSE,
)


class TestExtractDataflows:
    def test_parses_dataflows(self) -> None:
        result = extract_dataflows(SAMPLE_DATAFLOWS_RESPONSE)
        assert len(result) == 2
        assert result[0]["dataflow_id"] == "DF_CCI"
        assert result[0]["agency_id"] == "OECD"
        assert result[0]["name"] == "Consumer confidence indicator"
        assert result[0]["version"] == "1.0"
        assert result[0]["is_final"] is True

    def test_parses_second_dataflow(self) -> None:
        result = extract_dataflows(SAMPLE_DATAFLOWS_RESPONSE)
        assert result[1]["dataflow_id"] == "DF_KEI"
        assert result[1]["name"] == "Key Economic Indicators"

    def test_empty_response(self) -> None:
        result = extract_dataflows({"data": {"dataflows": []}})
        assert result == []

    def test_missing_dataflows_key(self) -> None:
        result = extract_dataflows({"data": {}})
        assert result == []


class TestExtractDimensions:
    def test_parses_dimensions(self) -> None:
        result = extract_dimensions(SAMPLE_DATASTRUCTURE_RESPONSE, dataflow_id="DF_CCI")
        assert len(result) >= 2
        dim_ids = [r["dimension_id"] for r in result]
        assert "REF_AREA" in dim_ids
        assert "INDICATOR" in dim_ids

    def test_dimension_names(self) -> None:
        result = extract_dimensions(SAMPLE_DATASTRUCTURE_RESPONSE, dataflow_id="DF_CCI")
        ref_area = [r for r in result if r["dimension_id"] == "REF_AREA"]
        assert ref_area[0]["dimension_name"] == "Reference area"

    def test_empty_datastructures(self) -> None:
        result = extract_dimensions({"data": {"dataStructures": []}})
        assert result == []


class TestExtractObservations:
    def test_parses_observations(self) -> None:
        result = extract_observations(
            SAMPLE_OBSERVATIONS_RESPONSE,
            country="ES",
            indicator_code="CCI",
            dataflow_id="DF_CCI",
        )
        assert len(result) == 3

    def test_observation_values(self) -> None:
        result = extract_observations(
            SAMPLE_OBSERVATIONS_RESPONSE,
            country="ES",
            indicator_code="CCI",
        )
        assert result[0]["value"] == 98.4
        assert result[1]["value"] == 99.1
        assert result[2]["value"] is None

    def test_observation_time_periods(self) -> None:
        result = extract_observations(
            SAMPLE_OBSERVATIONS_RESPONSE,
            country="ES",
            indicator_code="CCI",
        )
        assert result[0]["time_period"] == "2026-01"
        assert result[1]["time_period"] == "2026-02"
        assert result[2]["time_period"] == "2026-03"

    def test_observation_country_from_series(self) -> None:
        result = extract_observations(
            SAMPLE_OBSERVATIONS_RESPONSE,
            country="ES",
            indicator_code="CCI",
        )
        assert result[0]["country"] == "ES"

    def test_empty_datasets(self) -> None:
        empty_response = {
            "data": {
                "dataSets": [],
                "structure": {
                    "dimensions": {"series": [], "observation": []},
                    "attributes": {"observation": []},
                },
            }
        }
        result = extract_observations(empty_response, country="ES", indicator_code="CCI")
        assert result == []


def test_a_codelist_referenced_by_urn_is_still_found() -> None:
    """O SDMX da OCDE responde a referência como
    `urn:sdmx:org.sdmx.infomodel.codelist.Codelist=OECD:CL_AREA(1.0)`, e usar a
    URN inteira como id nunca casa com a codelist, que se chama `CL_AREA`.

    A falha era silenciosa e específica: a estrutura era buscada e gravada, as
    dimensões apareciam, e TODO código ficava nulo — inclusive a lista de
    países da dimensão REF_AREA, que é a única resposta à pergunta "esta fonte
    cobre este país?".
    """
    from app.utils.sdmx import extract_dimensions

    resposta = {
        "data": {
            "dataStructures": [
                {
                    "id": "DSD_AN_HOUSE_PRICES",
                    "dataStructureComponents": {
                        "dimensionList": {
                            "dimensions": [
                                {
                                    "id": "REF_AREA",
                                    "position": 0,
                                    "localRepresentation": {
                                        "enumeration": (
                                            "urn:sdmx:org.sdmx.infomodel.codelist."
                                            "Codelist=OECD:CL_AREA(1.0)"
                                        )
                                    },
                                }
                            ]
                        }
                    },
                }
            ],
            "codelists": [
                {
                    "id": "CL_AREA",
                    "codes": [{"id": "BRA", "name": "Brazil"}, {"id": "USA", "name": "United States"}],
                }
            ],
        }
    }

    dims = extract_dimensions(resposta, dataflow_id="DF_HOUSE_PRICES")

    assert [d["code_id"] for d in dims] == ["BRA", "USA"]


def test_a_codelist_referenced_by_plain_id_still_works() -> None:
    """A outra forma continua valendo — nem toda agência responde com URN."""
    from app.utils.sdmx import _codelist_id_de

    assert _codelist_id_de("CL_AREA") == "CL_AREA"
