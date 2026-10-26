"""Quando repetir uma chamada à fonte, e quanto esperar antes.

Este arquivo é igual, palavra por palavra, nos quatro coletores (World Bank,
OCDE, UN Data e Google Ads via DataForSEO). Até 26/10/2026 cada um tinha a sua
política -- exponencial sem jitter que repetia 429 mas não erro de rede, linear
que obedecia Retry-After, exponencial com jitter que não repetia 429, linear
com três tentativas -- e a mesma queda de fonte terminava de quatro jeitos
diferentes conforme quem coletava. A regra agora é uma só:

- repete 408, 429, todo 5xx, timeout e erro de rede: é a fonte ocupada ou fora
  do ar, e esperar é o que resolve;
- nunca repete os outros 4xx: a resposta não vai mudar, e repetir só atrasa a
  falha;
- espera em progressão exponencial (`default_backoff`, dobrando a cada
  tentativa, com teto) e com jitter, porque as chamadas saem em rajada e, sem
  ele, todas voltam no mesmo instante a uma fonte que já está sobrecarregada;
- quando a fonte diz quanto esperar (Retry-After), obedece -- até o mesmo teto.

O número de tentativas é `default_retries`, também igual nos quatro.
"""

import random

from app.core.config import settings

# Teto de uma espera. Sem ele, a quinta tentativa de uma fonte que pede
# Retry-After de dez minutos prenderia a coleta inteira.
MAX_BACKOFF_SECONDS = 60.0


def is_retryable_status(status: int | None) -> bool:
    """Se uma resposta com este status HTTP vale outra tentativa."""
    if status is None:
        return False
    return status in (408, 429) or status >= 500


def backoff_seconds(attempt: int, retry_after: str | None = None) -> float:
    """Quanto esperar depois da tentativa `attempt` (contada a partir de 1)."""
    if retry_after:
        try:
            return min(max(float(retry_after), 0.0), MAX_BACKOFF_SECONDS)
        except (TypeError, ValueError):
            # Retry-After também pode vir como data HTTP; aí vale a progressão.
            pass
    base = settings.default_backoff * (2 ** (attempt - 1))
    return min(base * random.uniform(1.0, 1.25), MAX_BACKOFF_SECONDS)
