from pydantic import BaseModel, Field, model_validator


class DataflowsRequest(BaseModel):
    agency_id: str = Field(default="OECD", description="Agency identifier", examples=["OECD"])
    detail: str = Field(default="allstubs", description="Detail level for the response", examples=["allstubs"])

    model_config = {
        "json_schema_extra": {
            "examples": [{"agency_id": "OECD", "detail": "allstubs"}]
        }
    }


class DatastructureRequest(BaseModel):
    agency_id: str = Field(default="OECD", description="Agency identifier", examples=["OECD"])
    dataflow_id: str = Field(..., min_length=1, description="Dataflow identifier", examples=["DF_CCI"])
    structure_id: str | None = Field(
        default=None, description="Data structure definition identifier", examples=["DSD_CCI"]
    )

    model_config = {
        "json_schema_extra": {
            "examples": [{"agency_id": "OECD", "dataflow_id": "DF_CCI", "structure_id": "DSD_CCI"}]
        }
    }


class ObservationsRequest(BaseModel):
    dataflow_id: str = Field(..., min_length=1, description="Dataflow identifier", examples=["DF_CCI"])
    dataset_id: str | None = Field(default=None, description="Dataset/DSD identifier", examples=["DSD_CCI"])
    country: str = Field(
        ..., min_length=2, max_length=3, pattern=r"^[A-Z]{2,3}$", description="ISO-2 or ISO-3 country code",
        examples=["ES"],
    )
    indicator_code: str = Field(..., min_length=1, description="Indicator code", examples=["CCI"])
    start_period: str | None = Field(default=None, description="Start period", examples=["2020"])
    end_period: str | None = Field(default=None, description="End period", examples=["2026"])
    frequency: str | None = Field(default=None, description="Frequency code (A, Q, M)", examples=["M"])
    query_key: str | None = Field(default=None, description="SDMX query key override")
    query_params: dict | None = Field(default=None, description="Additional query parameters")

    @model_validator(mode="after")
    def validate_periods(self) -> "ObservationsRequest":
        if self.start_period and self.end_period and self.start_period > self.end_period:
            raise ValueError("start_period must be <= end_period")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "dataflow_id": "DF_CCI",
                    "dataset_id": "DSD_CCI",
                    "country": "ES",
                    "indicator_code": "CCI",
                    "start_period": "2020",
                    "end_period": "2026",
                    "frequency": "M",
                }
            ]
        }
    }


class IndicatorCatalogItem(BaseModel):
    indicator_code: str = Field(..., min_length=1, description="Indicator code", examples=["CCI"])
    indicator_name: str = Field(
        ..., min_length=1, description="Indicator name", examples=["Consumer Confidence Indicator"]
    )
    description: str | None = Field(default=None, description="Indicator description")
    category: str = Field(..., description="Indicator category", examples=["consumer_confidence"])
    expected_unit: str | None = Field(default=None, description="Expected unit", examples=["index"])
    marketmind_dimension: str | None = Field(
        default=None, description="MarketMind dimension mapping", examples=["economic_readiness"]
    )
    dataflow_id: str | None = Field(default=None, description="OECD dataflow ID for this indicator")
    dataset_id: str | None = Field(default=None, description="OECD dataset/DSD ID for this indicator")
    is_active: bool = Field(default=True, description="Whether indicator is active")


class IndicatorCatalogRequest(BaseModel):
    indicators: list[IndicatorCatalogItem] = Field(..., min_length=1, description="List of indicators to upsert")

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "indicators": [
                        {
                            "indicator_code": "CCI",
                            "indicator_name": "Consumer Confidence Indicator",
                            "description": "Measures consumer confidence.",
                            "category": "consumer_confidence",
                            "expected_unit": "index",
                            "marketmind_dimension": "economic_readiness",
                            "is_active": True,
                        }
                    ]
                }
            ]
        }
    }


class IndicatorCollectRequest(BaseModel):
    country: str = Field(
        ..., min_length=2, max_length=3, pattern=r"^[A-Z]{2,3}$", description="ISO-2 or ISO-3 country code",
        examples=["ES"],
    )
    start_period: str | None = Field(default=None, description="Start period", examples=["2020"])
    end_period: str | None = Field(default=None, description="End period", examples=["2026"])
    indicator_codes: list[str] = Field(
        ..., min_length=1, description="List of indicator codes to collect", examples=[["CCI"]]
    )

    @model_validator(mode="after")
    def validate_periods(self) -> "IndicatorCollectRequest":
        if self.start_period and self.end_period and self.start_period > self.end_period:
            raise ValueError("start_period must be <= end_period")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "country": "ES",
                    "start_period": "2020",
                    "end_period": "2026",
                    "indicator_codes": ["CCI"],
                }
            ]
        }
    }


class RefreshStaleRequest(BaseModel):
    """Body of the daily maintenance pass. Every field has a default so the
    scheduled call can send `{}`."""

    stale_after_days: int = Field(
        default=30, ge=1, le=3650, description="A country whose last check is older than this gets collected again."
    )
    # Sem teto por padrão: None quer dizer "todo país vencido nesta passagem".
    # Um teto de 10 contra 24 países não conseguia sequer limpar o atraso de uma
    # noite — sobravam 14, que na noite seguinte disputavam as mesmas 10 vagas
    # com os que tinham acabado de vencer. O teto continua disponível para quem
    # quiser limitar uma partida a frio; ele só deixou de ser o padrão.
    limit: int | None = Field(default=None, ge=1, le=200, description="Most countries to refresh in one pass.")
    # Quando ligado, uma passagem que deixou país para trás responde 503 em vez
    # de 200. É o que transforma o CronJob em rede de segurança: `curl --fail`
    # sai diferente de zero, o Kubernetes retenta, e o que não se resolve fica
    # como Job `Failed` em vez de um sucesso que não coletou nada.
    fail_if_incomplete: bool = Field(
        default=False,
        description="Answer 503 when any country failed, so a caller that retries on error can retry.",
    )
    years_back: int = Field(
        default=5, ge=1, le=70, description="How far back the replayed window reaches, counting from this year."
    )
