"""Uma linha por período na leitura, e a coleta nova substituindo a velha na escrita."""

from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.dialects import postgresql

from app.repositories.oecd_observation_repository import OECDObservationRepository


def _sql(statement: object) -> str:
    return str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))  # type: ignore[attr-defined]


async def test_the_series_holds_one_value_per_period_from_the_latest_collection(mock_session: AsyncMock) -> None:
    """O MAX por período devolvia o número velho quando a fonte revisava para
    baixo. Vale a coleta mais recente; dentro dela, o maior valor."""
    result = MagicMock()
    result.all.return_value = []
    mock_session.execute = AsyncMock(return_value=result)

    await OECDObservationRepository(mock_session).series(country="ESP", measure="RHP", limit=12)

    sql = _sql(mock_session.execute.call_args.args[0])
    assert "DISTINCT ON (oecd_observations.time_period)" in sql
    assert (
        "ORDER BY oecd_observations.time_period DESC, oecd_observations.created_at DESC, "
        "oecd_observations.value DESC" in sql
    )


async def test_a_new_collection_replaces_the_periods_it_brings(mock_session: AsyncMock) -> None:
    records = [
        {"country": "ESP", "indicator_code": "RHP", "time_period": "2026-Q1", "value": 1},
        {"country": "ESP", "indicator_code": "RHP", "time_period": "2025-Q4", "value": 2},
    ]

    await OECDObservationRepository(mock_session).replace_periods(oecd_request_id="req", records=records)  # type: ignore[arg-type]

    sql = _sql(mock_session.execute.call_args.args[0])
    assert sql.startswith("DELETE FROM oecd_observations")
    assert "oecd_observations.time_period IN ('2025-Q4', '2026-Q1')" in sql
