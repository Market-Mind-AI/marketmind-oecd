from datetime import timedelta
from unittest.mock import AsyncMock

from app.repositories.freshness_repository import ObservationFacts
from app.services.oecd_service import OECDService
from app.utils.time import utc_now

_CPI = "CPI"
_RHP = "RHP"


def _service(mock_session: AsyncMock, *, checks: dict | None = None, observed: dict | None = None) -> OECDService:
    service = OECDService(mock_session)
    service._freshness_repo.last_checks = AsyncMock(return_value=checks or {})
    service._freshness_repo.observation_facts = AsyncMock(return_value=observed or {})
    return service


async def test_a_recent_check_is_not_stale(mock_session: AsyncMock) -> None:
    yesterday = utc_now() - timedelta(days=1)
    service = _service(mock_session, checks={("ESP", _CPI): yesterday})

    response = await service.get_freshness(countries=["ESP"], indicators=[_CPI])

    assert [(i.country, i.stale) for i in response.data.items] == [("ESP", False)]
    assert response.data.items[0].last_checked_at == yesterday


async def test_an_old_check_is_stale(mock_session: AsyncMock) -> None:
    service = _service(mock_session, checks={("ESP", _CPI): utc_now() - timedelta(days=91)})

    response = await service.get_freshness(countries=["ESP"], indicators=[_CPI])

    assert response.data.items[0].stale is True


async def test_a_slow_series_is_not_stale_just_because_the_period_is_old(mock_session: AsyncMock) -> None:
    service = _service(
        mock_session,
        checks={("ESP", _CPI): utc_now() - timedelta(days=2)},
        observed={
            ("ESP", _CPI): ObservationFacts(
                last_observation_at=utc_now() - timedelta(days=2), latest_period="2026-07", observation_count=36
            )
        },
    )

    response = await service.get_freshness(countries=["ESP"], indicators=[_CPI])

    assert response.data.items[0].latest_period == "2026-07"
    assert response.data.items[0].stale is False


async def test_a_pair_never_checked_is_reported_rather_than_omitted(mock_session: AsyncMock) -> None:
    service = _service(mock_session)

    response = await service.get_freshness(countries=["PER"], indicators=[_CPI])

    assert len(response.data.items) == 1
    assert response.data.items[0].last_checked_at is None
    assert response.data.items[0].stale is True


async def test_a_check_that_returned_nothing_still_counts_as_checked(mock_session: AsyncMock) -> None:
    """PER/ARG have no RHP at the OECD. Without this they would be re-fetched
    every day forever, and the analysis would burn its retry budget on a gap
    the source is never going to fill."""
    service = _service(mock_session, checks={("PER", _RHP): utc_now() - timedelta(days=3)})

    response = await service.get_freshness(countries=["PER"], indicators=[_RHP])

    item = response.data.items[0]
    assert item.observation_count == 0
    assert item.last_observation_at is None
    assert item.stale is False


async def test_only_stale_filters_out_what_is_fresh(mock_session: AsyncMock) -> None:
    service = _service(
        mock_session,
        checks={("ESP", _CPI): utc_now() - timedelta(days=1), ("ESP", _RHP): utc_now() - timedelta(days=91)},
    )

    response = await service.get_freshness(countries=["ESP"], indicators=[_CPI, _RHP], only_stale=True)

    assert [i.indicator_code for i in response.data.items] == [_RHP]


async def test_country_codes_are_normalised(mock_session: AsyncMock) -> None:
    service = _service(mock_session, checks={("ESP", _CPI): utc_now()})

    response = await service.get_freshness(countries=[" esp "], indicators=[_CPI])

    assert response.data.items[0].country == "ESP"
    assert response.data.items[0].stale is False


async def test_the_threshold_is_configurable(mock_session: AsyncMock) -> None:
    service = _service(mock_session, checks={("ESP", _CPI): utc_now() - timedelta(days=10)})

    fresh = await service.get_freshness(countries=["ESP"], indicators=[_CPI], stale_after_days=30)
    stale = await service.get_freshness(countries=["ESP"], indicators=[_CPI], stale_after_days=7)

    assert fresh.data.items[0].stale is False
    assert stale.data.items[0].stale is True


async def test_a_timestamp_that_comes_back_with_a_timezone_is_still_comparable(
    mock_session: AsyncMock,
) -> None:
    """The real failure, and every test here missed it by building naive
    datetimes by hand.

    `oecd_requests.created_at` is `timestamp with time zone`, so the database
    hands back an AWARE datetime, while `utc_now()` is naive. Comparing them is
    `TypeError: can't compare offset-naive and offset-aware datetimes`, and it
    took the whole endpoint down with a 500 — which took down this service's
    daily CronJob and the scoring service's macro prewarm with it, both showing
    up only as a pod in `Error`.
    """
    from datetime import UTC

    aware_yesterday = (utc_now() - timedelta(days=1)).replace(tzinfo=UTC)
    service = _service(mock_session, checks={("ESP", _CPI): aware_yesterday})

    response = await service.get_freshness(countries=["ESP"], indicators=[_CPI])

    assert [(i.country, i.stale) for i in response.data.items] == [("ESP", False)]


async def test_an_old_check_with_a_timezone_is_stale(mock_session: AsyncMock) -> None:
    """The other direction: normalising must not make everything look fresh."""
    from datetime import UTC

    aware_old = (utc_now() - timedelta(days=91)).replace(tzinfo=UTC)
    service = _service(mock_session, checks={("ESP", _CPI): aware_old})

    response = await service.get_freshness(countries=["ESP"], indicators=[_CPI])

    assert [(i.country, i.stale) for i in response.data.items] == [("ESP", True)]


async def test_the_default_window_is_the_cores_ninety_days(mock_session: AsyncMock) -> None:
    """Indicador de país sai uma vez por ano; o Core o considera bom por 90 dias
    (`country_indicator_ttl_days`). Com o padrão antigo de 30, quem não passava
    a janela renovava todo mês um número que não tinha mudado."""
    service = _service(mock_session, checks={("ESP", _CPI): utc_now() - timedelta(days=60)})

    response = await service.get_freshness(countries=["ESP"], indicators=[_CPI])

    assert response.data.stale_after_days == 90
    assert response.data.items[0].stale is False
