from datetime import UTC, datetime


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def as_naive_utc(moment: datetime | None) -> datetime | None:
    """Um instante comparável com `utc_now()`.

    Este serviço trata datetime sem fuso como UTC — é o que `utc_now()` devolve.
    Mas nem toda coluna guarda assim: `oecd_requests.created_at` é
    `timestamp with time zone` e volta COM fuso, e comparar um com o outro é
    `TypeError: can't compare offset-naive and offset-aware datetimes`.

    Derrubou o `/freshness` inteiro — que por sua vez derrubou o CronJob diário
    deste serviço e o pré-aquecimento macro do serviço de scoring, que passou a
    perguntar o frescor a quem é dono do dado. Nenhum dos dois falhava de forma
    visível: os dois só apareciam como um pod em `Error` na listagem.
    """
    if moment is None:
        return None
    return moment.astimezone(UTC).replace(tzinfo=None) if moment.tzinfo is not None else moment


def elapsed_ms(start: datetime) -> int:
    delta = utc_now() - start
    return int(delta.total_seconds() * 1000)
