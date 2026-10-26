from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    # Toda coluna de data é `timestamp with time zone` no banco (desde a
    # migração 001), e o modelo passa a dizer o mesmo. Declarada sem fuso, a
    # coluna fazia o driver tratar o instante como "sem fuso" na escrita --
    # o que obrigava `utc_now()` a devolver sem fuso, e cada comparação com o
    # que voltava do banco a converter antes. Ver app/utils/time.py.
    type_annotation_map = {datetime: DateTime(timezone=True)}
