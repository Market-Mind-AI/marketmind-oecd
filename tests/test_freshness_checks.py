"""Only a collection that finished counts as having checked the source."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.repositories.freshness_repository import CHECKED_STATUSES, FreshnessRepository


async def _sql_of_last_checks() -> str:
    session = AsyncMock()
    result = MagicMock()
    result.all.return_value = []
    session.execute.return_value = result
    await FreshnessRepository(session).last_checks(countries=["ES"], indicators=["X"])
    stmt = session.execute.call_args.args[0]
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


@pytest.mark.asyncio
async def test_a_failed_collection_is_not_a_check() -> None:
    """22/10/2026: a source outage failed twenty collections and the next pass
    saw all twenty as fresh, with their last real data a month old."""
    sql = await _sql_of_last_checks()

    assert "JOIN ingestion_runs" in sql
    assert "ingestion_runs.status IN ('success')" in sql


def test_only_finished_statuses_count() -> None:
    """"partial" saiu: nenhum coletor o gravava, e o Core o lê como falha."""
    assert CHECKED_STATUSES == ("success",)
