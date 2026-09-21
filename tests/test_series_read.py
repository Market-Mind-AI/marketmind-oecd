from decimal import Decimal
from unittest.mock import AsyncMock

from app.services.oecd_service import OECDService


def _service(mock_session: AsyncMock, rows: list) -> OECDService:
    service = OECDService(mock_session)
    service._observation_repo.series = AsyncMock(return_value=rows)
    return service


async def test_returns_one_point_per_period_newest_first(mock_session: AsyncMock) -> None:
    service = _service(mock_session, [("2026-Q2", Decimal("118.4")), ("2026-Q1", Decimal("117.1"))])

    response = await service.get_series(country="ESP", measure="RHP", frequency="Q")

    assert [(p.time_period, p.value) for p in response.data.points] == [
        ("2026-Q2", Decimal("118.4")),
        ("2026-Q1", Decimal("117.1")),
    ]


async def test_the_frequency_filter_reaches_the_query(mock_session: AsyncMock) -> None:
    """A measure published both quarterly and annually shares one code, and
    mixing them silently breaks any window counted in periods."""
    service = _service(mock_session, [])

    await service.get_series(country="ESP", measure="RHP", frequency="q")

    assert service._observation_repo.series.await_args.kwargs["frequency"] == "Q"


async def test_the_limit_is_passed_through(mock_session: AsyncMock) -> None:
    service = _service(mock_session, [])

    await service.get_series(country="ESP", measure="RHP", frequency="Q", limit=12)

    assert service._observation_repo.series.await_args.kwargs["limit"] == 12


async def test_a_country_with_nothing_stored_returns_an_empty_series(mock_session: AsyncMock) -> None:
    service = _service(mock_session, [])

    response = await service.get_series(country="PER", measure="RHP")

    assert response.data.points == []
    assert response.data.country == "PER"


async def test_filters_are_normalised(mock_session: AsyncMock) -> None:
    service = _service(mock_session, [])

    response = await service.get_series(country=" esp ", measure=" RHP ", frequency=" q ")

    assert response.data.country == "ESP"
    assert response.data.measure == "RHP"
    assert response.data.frequency == "Q"


async def test_measure_and_indicator_are_both_optional_filters(mock_session: AsyncMock) -> None:
    service = _service(mock_session, [])

    await service.get_series(country="ESP", indicator_code="REAL_HOUSE_PRICE")

    kwargs = service._observation_repo.series.await_args.kwargs
    assert kwargs["measure"] is None
    assert kwargs["indicator_code"] == "REAL_HOUSE_PRICE"
