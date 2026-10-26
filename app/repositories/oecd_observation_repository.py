import uuid
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.oecd_observation import OECDObservation
from app.utils.time import utc_now


class OECDObservationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def replace_periods(
        self, oecd_request_id: uuid.UUID, records: list[dict[str, Any]]
    ) -> list[OECDObservation]:
        """Grava uma coleta, substituindo o que já havia para os mesmos períodos.

        Até 26/10/2026 cada coleta só acrescentava, e um período coletado duas
        vezes ficava guardado duas vezes -- a leitura escondia isso com um MAX
        por período, que numa revisão para baixo devolvia o número velho. A
        coleta nova vence: é o número que a fonte publica hoje, revisões
        incluídas. Mesma regra nos três coletores de indicadores.

        A chave é (país, indicador, período), não a série SDMX inteira: uma
        coleta de um indicador traz de novo todas as séries dele, então
        substituir o período inteiro não perde nada.
        """
        entities: list[OECDObservation] = []
        now = utc_now()
        for record in records:
            entity = OECDObservation(
                id=uuid.uuid4(),
                oecd_request_id=oecd_request_id,
                dataset_id=record.get("dataset_id"),
                dataflow_id=record.get("dataflow_id"),
                country=record.get("country", ""),
                indicator_code=record.get("indicator_code", ""),
                indicator_name=record.get("indicator_name"),
                measure=record.get("measure"),
                unit=record.get("unit"),
                frequency=record.get("frequency"),
                time_period=record.get("time_period", ""),
                value=record.get("value"),
                normalized_value=record.get("normalized_value"),
                attributes=record.get("attributes"),
                created_at=now,
            )
            entities.append(entity)

        periodos: dict[tuple[str, str], set[str]] = {}
        for entity in entities:
            periodos.setdefault((entity.country, entity.indicator_code), set()).add(entity.time_period)
        for (country, indicator_code), periods in periodos.items():
            await self._session.execute(
                delete(OECDObservation)
                .where(OECDObservation.country == country)
                .where(OECDObservation.indicator_code == indicator_code)
                .where(OECDObservation.time_period.in_(sorted(periods)))
            )

        for entity in entities:
            self._session.add(entity)
        await self._session.flush()
        return entities

    async def get_by_oecd_request_id(self, oecd_request_id: uuid.UUID) -> list[OECDObservation]:
        result = await self._session.execute(
            select(OECDObservation).where(OECDObservation.oecd_request_id == oecd_request_id)
        )
        return list(result.scalars().all())

    async def series(
        self,
        *,
        country: str,
        measure: str | None = None,
        indicator_code: str | None = None,
        frequency: str | None = None,
        limit: int | None = None,
    ) -> list[tuple[str, Any]]:
        """One value per time period, newest first, nulls dropped.

        Um valor por período, e a regra de desempate é a mesma dos três
        coletores: vale a linha da coleta mais recente; dentro de uma mesma
        coleta, o maior valor. Isto não é cosmético. Um LIMIT 12 sobre a tabela
        crua já devolveu doze cópias do MESMO trimestre, o que fez a janela
        recente e a antiga ficarem idênticas e deu crescimento exatamente zero
        para todo país -- um número errado com cara de plausível.
        `replace_periods` impede a cópia na escrita; o que foi gravado antes
        dela, ou por duas coletas simultâneas, a leitura resolve aqui, e não
        em quem pergunta.

        "Dentro de uma mesma coleta" acontece: um indicador pode trazer várias
        séries SDMX que diferem só em dimensões que esta tabela não guarda, e
        o maior valor é o que este serviço sempre devolveu nesse caso.

        frequency matters: a measure published both quarterly and annually
        carries both under one code, and mixing them silently breaks any window
        counted in periods.
        """
        stmt = (
            select(OECDObservation.time_period, OECDObservation.value)
            .where(OECDObservation.country == country)
            .where(OECDObservation.value.is_not(None))
        )
        if measure is not None:
            stmt = stmt.where(OECDObservation.measure == measure)
        if indicator_code is not None:
            stmt = stmt.where(OECDObservation.indicator_code == indicator_code)
        if frequency is not None:
            stmt = stmt.where(OECDObservation.frequency == frequency)

        stmt = stmt.distinct(OECDObservation.time_period).order_by(
            OECDObservation.time_period.desc(),
            OECDObservation.created_at.desc(),
            OECDObservation.value.desc(),
        )
        if limit is not None:
            stmt = stmt.limit(limit)

        result = await self._session.execute(stmt)
        return [(row[0], row[1]) for row in result.all()]
