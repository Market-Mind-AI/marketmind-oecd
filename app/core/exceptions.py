class OECDClientError(Exception):
    """A fonte respondeu, e a resposta não serve: um 4xx que não é 404, uma
    recusa do pedido. Repetir não muda a resposta, então não se repete (502)."""


class OECDTransientError(Exception):
    """A fonte está ocupada ou fora do ar (5xx, 429, timeout, rede) e continuou
    assim depois de todas as tentativas. 503 em todos os coletores: quer dizer
    "tente de novo mais tarde", que é exatamente o que vale fazer.

    Não herda de OECDClientError. Herdava até 26/10/2026, e por isso uma queda
    da fonte saía como 502 -- o mesmo status de uma resposta que não serve --
    enquanto os outros coletores respondiam 503."""


class OECDTimeoutError(OECDTransientError):
    pass


class OECDRateLimitError(OECDTransientError):
    pass


class OECDEmptyResponseError(Exception):
    """A fonte disse, de forma definitiva, que não tem o dado (404). Numa coleta
    de indicadores isso é uma resposta -- conta como verificação -- e não uma
    falha."""


class OECDParsingError(Exception):
    pass


class IndicatorNotConfiguredError(Exception):
    """O pedido nomeia um indicador que este serviço não sabe coletar. É erro de
    quem pediu, o único caso de 4xx de uma coleta -- e o mesmo 422 nos três
    coletores de indicadores."""
