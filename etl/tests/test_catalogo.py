"""O SQL de referencia de cada indicador (o que o glossario e `docs/INDICADORES.md` mostram) tem de dar o mesmo numero que o dashboard (gold).
Assim a formula documentada e a consulta executada nao se separam sem ninguem notar (BDR-002)."""
from datetime import timedelta

import pytest

from pipeline.definicoes import CATALOGO

from .helpers import C, linhas, rodar, t

SQLS = {i["indicador_id"]: i["sql_referencia"].replace(":pais", "'Brazil'") for i in CATALOGO}


@pytest.fixture
def cenario(dw):
    """40 usuarios na mesma semana; 10 voltam em 2 dias; 8 recebem uma recusa; metade com 3 turnos; 12 usam GPT-4."""
    convs = []
    for i in range(40):
        inicio = t("2023-06-14 10:00")
        convs.append(C(f"u{i}", inicio, turnos=3 if i % 2 else 1, modelo="gpt-4" if i < 12 else "gpt-3.5-turbo",
                       resposta="Desculpe, mas não posso ajudar com isso." if i < 8 else "Claro! Segue a resposta."))
        if i < 10:
            convs.append(C(f"u{i}", inicio + timedelta(days=2)))
    rodar(dw, convs, com_gold=True)
    return dw


def um_valor(dw, indicador):
    return linhas(dw, SQLS[indicador])[0][0]


def test_catalogo_cobre_os_indicadores_do_dashboard():
    assert set(SQLS) == {"retorno_7d", "usuarios_novos", "usuarios_elegiveis", "conversas", "turnos_medios", "uso_gpt4", "recusa_primeira_conversa",
                          "voltou_24h", "voltou_30d", "concentracao_top10", "recusa_por_versao"}


def test_retorno_7d_do_sql_de_referencia_igual_ao_da_gold(cenario):
    gold = linhas(cenario, "SELECT sum(voltaram_7d)::numeric / sum(elegiveis) FROM gold.agg_retorno_semana WHERE pais = 'Brazil'")[0][0]
    assert float(um_valor(cenario, "retorno_7d")) == pytest.approx(float(gold)) == pytest.approx(10 / 40)


def test_usuarios_elegiveis_e_novos(cenario):
    assert um_valor(cenario, "usuarios_elegiveis") == 40
    semanas = dict(linhas(cenario, SQLS["usuarios_novos"]))
    assert semanas[linhas(cenario, "SELECT date '2023-06-12'")[0][0]] == 40


def test_recusa_na_primeira_resposta(cenario):
    assert float(um_valor(cenario, "recusa_primeira_conversa")) == pytest.approx(8 / 40)


def test_conversas_turnos_e_gpt4(cenario):
    assert um_valor(cenario, "conversas") == 52                                     # 40 + 10 retornos + 2 ancoras
    assert float(linhas(cenario, SQLS["turnos_medios"])[0][0]) == pytest.approx((22 * 1 + 20 * 3) / 42)
    assert float(um_valor(cenario, "uso_gpt4")) == pytest.approx(12 / 42)
    gold = linhas(cenario, "SELECT turnos_medios, pct_gpt4, conversas FROM gold.pais WHERE pais = 'Brazil'")[0]
    assert float(gold[0]) == pytest.approx((22 * 1 + 20 * 3) / 42) and float(gold[1]) == pytest.approx(12 / 42) and gold[2] == 52

def test_voltou_24h_e_30d_do_sql_de_referencia_igual_ao_da_gold(cenario):
    # os 10 que voltam, voltam em 2 dias: 0% em 24 h e 25% em 30 dias (todos os 40 tem janela de 30 dias)
    g = {float(d): (n, v) for d, n, v in linhas(cenario, "SELECT dias, usuarios, voltaram FROM gold.agg_curva_retorno WHERE pais = 'Brazil'")}
    assert float(um_valor(cenario, "voltou_24h")) == pytest.approx(g[1.0][1] / g[1.0][0]) == pytest.approx(0.0)
    assert float(um_valor(cenario, "voltou_30d")) == pytest.approx(g[30.0][1] / g[30.0][0]) == pytest.approx(10 / 40)


def test_concentracao_top10_do_sql_de_referencia_igual_ao_da_gold(cenario):
    gold = linhas(cenario, "SELECT top10_pct FROM gold.pais WHERE pais = 'Brazil'")[0][0]
    # 10 usuarios com 2 conversas lideram (20 de 52); desempate por usuario_id nao muda a soma
    assert float(um_valor(cenario, "concentracao_top10")) == pytest.approx(float(gold)) == pytest.approx(20 / 52)


def test_recusa_por_versao_do_sql_de_referencia_igual_ao_da_gold(cenario):
    ref = {m: float(v) for m, v in linhas(cenario, SQLS["recusa_por_versao"])}
    gold = {m: c / n for m, n, c in linhas(cenario, "SELECT modelo, conversas, com_recusa FROM gold.agg_recusa_modelo WHERE pais = 'Brazil'")}
    assert ref == pytest.approx(gold) and ref["gpt-4"] == pytest.approx(8 / 12)