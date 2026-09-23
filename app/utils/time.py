from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def as_naive_utc(value: datetime | None) -> datetime | None:
    """A datetime on the same footing as utc_now(), whatever it arrived as.

    utc_now() is naive, but the columns these values come back from are
    `timestamp with time zone`, so the driver hands them back aware. Comparing
    one against the other raises TypeError, which is what answered 500 to every
    freshness check for a country that had been fetched before. Anything read
    from the database and compared against utc_now() goes through here first.
    """
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def elapsed_ms(start: datetime) -> int:
    delta = utc_now() - start
    return int(delta.total_seconds() * 1000)
