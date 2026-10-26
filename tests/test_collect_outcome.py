"""O que uma coleta de indicadores responde, e o que ela conta como verificação.

As regras são as mesmas nos três coletores de indicadores."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.routes.oecd import _handle_exception
from app.core.exceptions import (
    IndicatorNotConfiguredError,
    OECDClientError,
    OECDEmptyResponseError,
    OECDTimeoutError,
    OECDTransientError,
)
from app.schemas.requests import IndicatorCollectRequest
from app.services.oecd_service import OECDService

_RHP = "RHP"
_CPI = "CPI"
_FLOWS = {_RHP: "DSD_AN_HOUSE_PRICES@DF_HOUSE_PRICES", _CPI: "DSD_PRICES@DF_PRICES_ALL"}


def _service(mock_session: AsyncMock, *outcomes: object, codes: tuple[str, ...] = (_RHP, _CPI)) -> OECDService:
    service = OECDService(mock_session)
    service._indicator_repo.get_by_codes = AsyncMock(
        return_value=[
            SimpleNamespace(indicator_code=code, dataflow_id=_FLOWS.get(code), dataset_id=None) for code in codes
        ]
    )
    service._ingestion_repo = MagicMock(create=AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))
    service._ingestion_repo.mark_success = AsyncMock()
    service._ingestion_repo.mark_failed = AsyncMock()
    service._oecd_request_repo = MagicMock(create=AsyncMock(side_effect=lambda **kw: SimpleNamespace(id=uuid.uuid4(), **kw)))
    service._raw_response_repo = MagicMock(create=AsyncMock())
    service._observation_repo = MagicMock(replace_periods=AsyncMock())
    service._client = MagicMock(get_observations=AsyncMock(side_effect=list(outcomes)))
    return service


def _request(*codes: str) -> IndicatorCollectRequest:
    return IndicatorCollectRequest(country="ESP", start_period="2016", end_period="2026", indicator_codes=list(codes))


def _checks(service: OECDService) -> list[str]:
    return [call.kwargs["indicator_code"] for call in service._oecd_request_repo.create.await_args_list]


async def test_the_source_being_down_for_every_indicator_is_a_503(mock_session: AsyncMock) -> None:
    """Era um 200 com a execução marcada como falha por dentro, e a manutenção
    diária contava a queda como país renovado."""
    service = _service(mock_session, OECDTransientError("502"), OECDTimeoutError("timeout"))

    with pytest.raises(OECDTransientError) as raised:
        await service.collect_indicators(_request(_RHP, _CPI))

    assert _handle_exception(raised.value).status_code == 503
    service._ingestion_repo.mark_failed.assert_awaited_once()
    assert _checks(service) == []


async def test_nothing_collected_for_another_reason_is_a_502(mock_session: AsyncMock) -> None:
    service = _service(mock_session, OECDTransientError("502"), OECDClientError("400"))

    with pytest.raises(OECDClientError) as raised:
        await service.collect_indicators(_request(_RHP, _CPI))

    assert _handle_exception(raised.value).status_code == 502


async def test_an_unknown_indicator_is_a_422_before_anything_is_collected(mock_session: AsyncMock) -> None:
    service = _service(mock_session, codes=(_RHP,))

    with pytest.raises(IndicatorNotConfiguredError) as raised:
        await service.collect_indicators(_request(_RHP, "NOPE"))

    assert _handle_exception(raised.value).status_code == 422
    service._client.get_observations.assert_not_awaited()
    service._ingestion_repo.create.assert_not_awaited()


async def test_an_indicator_without_a_dataflow_is_a_422(mock_session: AsyncMock) -> None:
    service = _service(mock_session, codes=(_RHP, "UNEMP"))

    with pytest.raises(IndicatorNotConfiguredError):
        await service.collect_indicators(_request(_RHP, "UNEMP"))


async def test_the_source_having_no_data_is_an_answer_and_a_check(mock_session: AsyncMock) -> None:
    """Um 404 da OCDE era exceção: sem linha de verificação, o par era
    recoletado toda noite. "Não tenho" é resposta definitiva."""
    service = _service(mock_session, OECDEmptyResponseError("404"), codes=(_RHP,))

    response = await service.collect_indicators(_request(_RHP))

    assert response.data.indicators_collected == [_RHP]
    assert response.data.indicators_failed == []
    assert _checks(service) == [_RHP]


async def test_only_the_indicators_that_got_an_answer_are_checks(mock_session: AsyncMock) -> None:
    service = _service(mock_session, ({"data": {}}, "url"), OECDTransientError("502"))

    response = await service.collect_indicators(_request(_RHP, _CPI))

    assert _checks(service) == [_RHP]
    assert response.data.indicators_failed == [_CPI]
    service._ingestion_repo.mark_success.assert_awaited_once()


def test_unexpected_errors_are_still_500() -> None:
    assert isinstance(_handle_exception(RuntimeError("x")), HTTPException)
    assert _handle_exception(RuntimeError("x")).status_code == 500
