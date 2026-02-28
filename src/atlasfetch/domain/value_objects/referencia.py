"""Value Object: referência de fatura (MM/YYYY)."""


def parse_referencia(referencia: str) -> tuple[int, int] | None:
    """
    Extrai (ano, mes) de referencia no formato MM/YYYY.
    Retorna None se inválido.
    """
    try:
        parts = referencia.strip().split("/")
        if len(parts) == 2:
            mes = int(parts[0])
            ano = int(parts[1])
            if 1 <= mes <= 12 and ano > 2000:
                return (ano, mes)
    except (ValueError, IndexError):
        pass
    return None


def referencia_match(referencia: str, ano: int, mes: int) -> bool:
    """Verifica se referencia (ex: 01/2026) corresponde ao ano/mês."""
    parsed = parse_referencia(referencia)
    if parsed:
        ref_ano, ref_mes = parsed  # (ano, mes) de parse_referencia
        return ref_ano == ano and ref_mes == mes
    return True
