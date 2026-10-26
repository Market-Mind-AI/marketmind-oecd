from datetime import UTC, datetime


def utc_now() -> datetime:
    """Agora, em UTC e COM fuso -- a única convenção de instante deste serviço.

    As colunas de data são todas `timestamp with time zone`, e voltam do banco
    com fuso. Enquanto este relógio devolvia o instante sem fuso, comparar um
    com o outro era `TypeError: can't compare offset-naive and offset-aware
    datetimes` -- derrubou o /freshness da OCDE e o do World Bank, um de cada
    vez -- e cada serviço remendava com uma conversão própria no ponto da
    comparação. Com o fuso desde a origem, não há o que converter. É a mesma
    convenção nos quatro coletores.
    """
    return datetime.now(UTC)


def elapsed_ms(start: datetime) -> int:
    delta = utc_now() - start
    return int(delta.total_seconds() * 1000)
