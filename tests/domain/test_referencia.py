from atlasfetch.domain.value_objects.referencia import parse_referencia, referencia_match


def test_parse_referencia_valida():
    assert parse_referencia("03/2026") == (2026, 3)


def test_parse_referencia_invalida_retorna_none():
    assert parse_referencia("13/2026") is None
    assert parse_referencia("texto") is None


def test_referencia_match_aceita_referencia_invalida_para_nao_descartar_dados():
    assert referencia_match("referencia-desconhecida", 2026, 3) is True


def test_referencia_match_compara_ano_e_mes_quando_formato_eh_valido():
    assert referencia_match("03/2026", 2026, 3) is True
    assert referencia_match("02/2026", 2026, 3) is False