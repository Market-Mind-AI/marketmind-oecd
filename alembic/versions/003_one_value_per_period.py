"""One value per period: drop the copies that repeated collections left behind

Até 26/10/2026 cada coleta só acrescentava observações, e um período coletado
duas vezes ficava guardado duas vezes; a leitura escondia isso com um MAX por
período, que numa revisão para baixo devolvia o número velho. A coleta agora
substitui os períodos que traz (`replace_periods`), e esta migração limpa o que
ficou de antes, com a mesma regra: para cada (país, indicador, período) ficam
as linhas da coleta mais recente.

O índice cobre a série como ela é lida e substituída: país, indicador, período.

Revision ID: 003
Revises: 002
Create Date: 2026-10-26

"""

from collections.abc import Sequence

from alembic import op

revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM oecd_observations AS antiga
        USING oecd_observations AS nova
        WHERE nova.country = antiga.country
          AND nova.indicator_code = antiga.indicator_code
          AND nova.time_period = antiga.time_period
          AND nova.created_at > antiga.created_at
        """
    )
    op.create_index(
        "ix_oecd_observations_series",
        "oecd_observations",
        ["country", "indicator_code", "time_period"],
    )


def downgrade() -> None:
    # As cópias apagadas não voltam: eram o mesmo período guardado de novo.
    op.drop_index("ix_oecd_observations_series", table_name="oecd_observations")
