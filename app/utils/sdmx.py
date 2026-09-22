from typing import Any

from app.core.exceptions import OECDParsingError


def extract_dataflows(response: dict[str, Any]) -> list[dict[str, Any]]:
    dataflows: list[dict[str, Any]] = []
    try:
        structures = response.get("data", response)
        df_list = structures.get("dataflows", [])
        for df in df_list:
            name = _extract_localized_name(df.get("name"))
            description = _extract_localized_name(df.get("description"))
            dataflows.append(
                {
                    "agency_id": df.get("agencyID"),
                    "dataflow_id": df.get("id", ""),
                    "name": name,
                    "description": description,
                    "version": df.get("version"),
                    "is_final": df.get("isFinal"),
                    "raw_payload": df,
                }
            )
    except Exception as e:
        raise OECDParsingError(f"Failed to parse dataflows: {e}") from e
    return dataflows


def extract_dimensions(response: dict[str, Any], dataflow_id: str | None = None) -> list[dict[str, Any]]:
    dimensions: list[dict[str, Any]] = []
    try:
        structures = response.get("data", response)
        dsd_list = structures.get("dataStructures", [])
        if not dsd_list:
            return dimensions

        dsd = dsd_list[0]
        structure_id = dsd.get("id")
        components = dsd.get("dataStructureComponents", {})
        dim_list = components.get("dimensionList", {}).get("dimensions", [])

        for dim in dim_list:
            dim_id = dim.get("id", "")
            dim_name = _extract_localized_name(dim.get("name"))
            position = dim.get("position")
            codes = _extract_codelist_codes(dim, response)
            if codes:
                for code in codes:
                    dimensions.append(
                        {
                            "dataflow_id": dataflow_id,
                            "structure_id": structure_id,
                            "dimension_id": dim_id,
                            "dimension_name": dim_name,
                            "dimension_position": position,
                            "code_id": code["code_id"],
                            "code_name": code["code_name"],
                        }
                    )
            else:
                dimensions.append(
                    {
                        "dataflow_id": dataflow_id,
                        "structure_id": structure_id,
                        "dimension_id": dim_id,
                        "dimension_name": dim_name,
                        "dimension_position": position,
                        "code_id": None,
                        "code_name": None,
                    }
                )
    except Exception as e:
        raise OECDParsingError(f"Failed to parse datastructure: {e}") from e
    return dimensions


def extract_observations(
    response: dict[str, Any],
    country: str,
    indicator_code: str,
    dataflow_id: str | None = None,
    dataset_id: str | None = None,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    try:
        data_sets = response.get("data", response).get("dataSets", [])
        structure = response.get("data", response).get("structure", {})

        dim_keys = _build_dimension_keys(structure)
        obs_dim_keys = _build_observation_dimension_keys(structure)
        attr_keys = _build_attribute_keys(structure)

        for ds in data_sets:
            series_map = ds.get("series", {})
            if series_map:
                observations.extend(
                    _parse_series(
                        series_map, dim_keys, obs_dim_keys, attr_keys,
                        country, indicator_code, dataflow_id, dataset_id,
                    )
                )
            else:
                flat_obs = ds.get("observations", {})
                if flat_obs:
                    observations.extend(
                        _parse_flat_observations(
                            flat_obs, dim_keys, obs_dim_keys, attr_keys,
                            country, indicator_code, dataflow_id, dataset_id,
                        )
                    )
    except Exception as e:
        raise OECDParsingError(f"Failed to parse observations: {e}") from e
    return observations


def _parse_series(
    series_map: dict,
    dim_keys: list[dict],
    obs_dim_keys: list[dict],
    attr_keys: list[dict],
    country: str,
    indicator_code: str,
    dataflow_id: str | None,
    dataset_id: str | None,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for series_key, series_data in series_map.items():
        series_dims = _resolve_series_dimensions(series_key, dim_keys)
        series_country = series_dims.get("REF_AREA", country)
        series_indicator = series_dims.get("INDICATOR", series_dims.get("SUBJECT", indicator_code))
        series_measure = series_dims.get("MEASURE", series_dims.get("UNIT_MEASURE"))
        series_freq = series_dims.get("FREQ", series_dims.get("FREQUENCY"))
        series_unit = series_dims.get("UNIT_MULT", series_dims.get("UNIT", series_dims.get("UNIT_MEASURE")))

        obs_map = series_data.get("observations", {})
        for obs_key, obs_values in obs_map.items():
            time_period = _resolve_time_period(obs_key, obs_dim_keys)
            value = obs_values[0] if obs_values and obs_values[0] is not None else None

            observations.append(
                {
                    "dataset_id": dataset_id,
                    "dataflow_id": dataflow_id,
                    "country": series_country,
                    "indicator_code": series_indicator or indicator_code,
                    "indicator_name": None,
                    "measure": series_measure,
                    "unit": series_unit,
                    "frequency": series_freq,
                    "time_period": time_period or obs_key,
                    "value": value,
                    "attributes": _resolve_attributes(obs_values, attr_keys),
                }
            )
    return observations


def _parse_flat_observations(
    flat_obs: dict,
    dim_keys: list[dict],
    obs_dim_keys: list[dict],
    attr_keys: list[dict],
    country: str,
    indicator_code: str,
    dataflow_id: str | None,
    dataset_id: str | None,
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    all_dims = dim_keys + obs_dim_keys
    for obs_key, obs_values in flat_obs.items():
        resolved = _resolve_flat_dimensions(obs_key, all_dims)
        time_period = resolved.get("TIME_PERIOD", obs_key)
        value = obs_values[0] if obs_values and obs_values[0] is not None else None

        observations.append(
            {
                "dataset_id": dataset_id,
                "dataflow_id": dataflow_id,
                "country": resolved.get("REF_AREA", country),
                "indicator_code": resolved.get("INDICATOR", resolved.get("SUBJECT", indicator_code)),
                "indicator_name": None,
                "measure": resolved.get("MEASURE"),
                "unit": resolved.get("UNIT_MULT", resolved.get("UNIT")),
                "frequency": resolved.get("FREQ", resolved.get("FREQUENCY")),
                "time_period": time_period,
                "value": value,
                "attributes": _resolve_attributes(obs_values, attr_keys),
            }
        )
    return observations


def _build_dimension_keys(structure: dict[str, Any]) -> list[dict[str, Any]]:
    dims = structure.get("dimensions", {}).get("series", [])
    return [
        {
            "id": d.get("id", ""),
            "name": _extract_localized_name(d.get("name")),
            "values": d.get("values", []),
            "position": d.get("keyPosition"),
        }
        for d in dims
    ]


def _build_observation_dimension_keys(structure: dict[str, Any]) -> list[dict[str, Any]]:
    dims = structure.get("dimensions", {}).get("observation", [])
    return [
        {
            "id": d.get("id", ""),
            "name": _extract_localized_name(d.get("name")),
            "values": d.get("values", []),
            "position": d.get("keyPosition"),
        }
        for d in dims
    ]


def _build_attribute_keys(structure: dict[str, Any]) -> list[dict[str, Any]]:
    attrs = structure.get("attributes", {}).get("observation", [])
    return [
        {
            "id": a.get("id", ""),
            "name": _extract_localized_name(a.get("name")),
            "values": a.get("values", []),
        }
        for a in attrs
    ]


def _resolve_series_dimensions(series_key: str, dim_keys: list[dict]) -> dict[str, str]:
    parts = series_key.split(":")
    result: dict[str, str] = {}
    for i, part in enumerate(parts):
        if i < len(dim_keys) and part:
            dim = dim_keys[i]
            idx = int(part) if part.isdigit() else -1
            values = dim.get("values", [])
            if 0 <= idx < len(values):
                result[dim["id"]] = values[idx].get("id", part)
            else:
                result[dim["id"]] = part
    return result


def _resolve_time_period(obs_key: str, obs_dim_keys: list[dict]) -> str | None:
    if not obs_dim_keys:
        return None
    time_dim = obs_dim_keys[0]
    values = time_dim.get("values", [])
    idx = int(obs_key) if obs_key.isdigit() else -1
    if 0 <= idx < len(values):
        return values[idx].get("id", values[idx].get("name", obs_key))
    return obs_key


def _resolve_flat_dimensions(obs_key: str, all_dims: list[dict]) -> dict[str, str]:
    parts = obs_key.split(":")
    result: dict[str, str] = {}
    for i, part in enumerate(parts):
        if i < len(all_dims) and part:
            dim = all_dims[i]
            idx = int(part) if part.isdigit() else -1
            values = dim.get("values", [])
            if 0 <= idx < len(values):
                result[dim["id"]] = values[idx].get("id", part)
            else:
                result[dim["id"]] = part
    return result


def _resolve_attributes(obs_values: list, attr_keys: list[dict]) -> dict[str, str] | None:
    if len(obs_values) <= 1 or not attr_keys:
        return None
    attrs: dict[str, str] = {}
    for i, attr_val in enumerate(obs_values[1:]):
        if attr_val is not None and i < len(attr_keys):
            attr = attr_keys[i]
            values = attr.get("values", [])
            idx = int(attr_val) if isinstance(attr_val, (int, float)) else -1
            if 0 <= idx < len(values):
                attrs[attr["id"]] = values[idx].get("id", str(attr_val))
            else:
                attrs[attr["id"]] = str(attr_val)
    return attrs if attrs else None


def _extract_localized_name(name_field: Any) -> str | None:
    if name_field is None:
        return None
    if isinstance(name_field, str):
        return name_field
    if isinstance(name_field, dict):
        return name_field.get("en", name_field.get("en-US", next(iter(name_field.values()), None)))
    return str(name_field)


def _codelist_id_de(enumeration: str) -> str:
    """O id da codelist, venha ele solto ou dentro de uma URN.

    O SDMX da OCDE responde a referência como
    `urn:sdmx:org.sdmx.infomodel.codelist.Codelist=OECD:CL_AREA(1.0)`, e usar
    isso inteiro como id nunca casa com a codelist, que se chama `CL_AREA`. O
    efeito era silencioso e específico: a estrutura era buscada e gravada, as
    dimensões apareciam, e TODO código ficava nulo — inclusive a lista de países
    que a dimensão REF_AREA carrega, que é a única resposta à pergunta "esta
    fonte cobre este país?".
    """
    if "=" not in enumeration:
        return enumeration
    depois = enumeration.rsplit("=", 1)[1]
    sem_agencia = depois.split(":")[-1]
    return sem_agencia.split("(")[0]


def _extract_codelist_codes(dimension: dict, response: dict) -> list[dict[str, str | None]]:
    local_repr = dimension.get("localRepresentation", {})
    enum_ref = local_repr.get("enumeration")
    if not enum_ref:
        return []

    codelist_id = _codelist_id_de(enum_ref) if isinstance(enum_ref, str) else enum_ref.get("id")
    if not codelist_id:
        return []

    structures = response.get("data", response)
    codelists = structures.get("codelists", [])
    for cl in codelists:
        if cl.get("id") == codelist_id:
            return [
                {
                    "code_id": code.get("id", ""),
                    "code_name": _extract_localized_name(code.get("name")),
                }
                for code in cl.get("codes", [])
            ]
    return []
