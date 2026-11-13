"""Analise ampliada (migracao 018): voltou em 24 h, curva de retorno, concentracao, uso por hora, modelo e recusa por versao.
Cada teste fixa UMA regra de borda das novas metricas."""
from datetime import timedelta

import pytest

from .helpers import C, linhas, rodar, t, usuario

BASE = t("2023-06-01 10:00")


def test_voltou_24h_no_limite(dw):
    rodar(dw, [C("exato", BASE), C("exato", BASE + timedelta(days=1)),                              # 24 h exatas: conta
               C("passou", BASE), C("passou", BASE + timedelta(days=1, seconds=1))])                # 1 s depois: nao conta em 24 h, mas conta em 7 dias
    assert usuario(dw, "exato")["voltou_24h"] is True
    p = usuario(dw, "passou")
    assert p["voltou_24h"] is False and p["voltou_7d"] is True


def test_voltou_24h_implica_voltou_7d_e_dias_ate_voltar(dw):
    rodar(dw, [C("a", BASE), C("a", BASE + timedelta(hours=12)), C("b", BASE), C("b", BASE + timedelta(days=3)), C("c", BASE)])
    a, b, c = usuario(dw, "a"), usuario(dw, "b"), usuario(dw, "c")
    assert float(a["dias_ate_voltar"]) == pytest.approx(0.5) and a["voltou_24h"] and a["voltou_7d"]
    assert float(b["dias_ate_voltar"]) == pytest.approx(3.0) and not b["voltou_24h"] and b["voltou_7d"]
    assert c["dias_ate_voltar"] is None and not c["voltou_24h"] and not c["voltou_7d"]
    assert linhas(dw, "SELECT count(*) FROM silver.fato_usuario WHERE voltou_24h AND NOT voltou_7d")[0][0] == 0


def test_janela_de_30_dias_completa(dw):
    # ancoras: 2023-01-01 e 2023-12-31. Precisa da 1a vez >= inicio+30 dias e <= fim-30 dias
    rodar(dw, [C("cedo", t("2023-01-15 10:00")), C("meio", BASE), C("tarde", t("2023-12-10 10:00"))])
    assert (usuario(dw, "cedo")["janela_30d"], usuario(dw, "meio")["janela_30d"], usuario(dw, "tarde")["janela_30d"]) == (False, True, False)


def test_curva_de_retorno_e_monotonica_e_usa_so_quem_tem_janela(dw):
    convs = [C("a", BASE), C("a", BASE + timedelta(hours=12)), C("b", BASE), C("b", BASE + timedelta(days=2)),
             C("c", BASE), C("d", BASE), C("d", BASE + timedelta(days=10)), C("tarde", t("2023-12-10 10:00"))]
    rodar(dw, convs, com_gold=True)
    curva = {float(d): (n, v) for d, n, v in linhas(dw, "SELECT dias, usuarios, voltaram FROM gold.agg_curva_retorno WHERE pais = 'Brazil'")}
    assert curva[0.5] == (4, 1) and curva[2.0] == (4, 2) and curva[7.0] == (4, 2) and curva[10.0] == (4, 3) and curva[30.0] == (4, 3)
    voltaram = [v for _, (_, v) in sorted(curva.items())]
    assert voltaram == sorted(voltaram)


def test_idioma_do_navegador(dw):
    rodar(dw, [C("pt", BASE, extras={"al": "pt-BR,pt;q=0.9,en;q=0.8"}), C("sem", BASE)])
    assert usuario(dw, "pt")["idioma_navegador"] == "pt-br" and usuario(dw, "sem")["idioma_navegador"] == ""


def test_fator_idioma_x_navegador_e_dispositivo(dw):
    rodar(dw, [C("p", BASE, extras={"al": "pt-BR"}), C("en", BASE, idioma="English", extras={"al": "pt-BR"}),
               C("ru", BASE, idioma="Russian", extras={"al": "pt-BR"}), C("cel", BASE, ua="Mozilla/5.0 (Linux; Android 13; SM-S908B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36")], com_gold=True)
    idi = dict(linhas(dw, "SELECT nivel, elegiveis FROM gold.agg_retorno_fator WHERE pais = 'Brazil' AND fator = 'idioma_x_navegador'"))
    assert idi == {"Pedido no idioma do navegador": 1,                                   # so "p"; "cel" nao tem accept-language e fica de fora
                   "Inglês (navegador em outro idioma)": 1,
                   "Outro idioma (nem o do navegador, nem inglês)": 1}
    disp = dict(linhas(dw, "SELECT nivel, elegiveis FROM gold.agg_retorno_fator WHERE pais = 'Brazil' AND fator = 'dispositivo'"))
    assert disp == {"Celular": 1, "Computador": 3}

def test_concentracao_por_faixa(dw):
    convs = [C("um", BASE)] + [C("tres", BASE + timedelta(hours=i)) for i in range(3)] + [C("cinco", BASE + timedelta(hours=i)) for i in range(5)]
    rodar(dw, convs, com_gold=True)
    faixas = {f: (n, c) for f, n, c in linhas(dw, "SELECT faixa, usuarios, conversas FROM gold.agg_concentracao WHERE pais = 'Brazil'")}
    assert faixas == {"1": (3, 3), "2-3": (1, 3), "4-10": (1, 5)}                 # 3 usuarios de 1 conversa = 2 ancoras + "um"
    top10, maior, um = linhas(dw, "SELECT top10_pct, maior_pct, pessoas_1_conversa_pct FROM gold.pais WHERE pais = 'Brazil'")[0]
    assert float(top10) == pytest.approx(1.0) and float(maior) == pytest.approx(5 / 11) and float(um) == pytest.approx(3 / 5)


def test_uso_por_hora_no_fuso_do_pais(dw):
    # 01:30 UTC de quarta (2023-06-14) = 22:30 de terca em Sao Paulo (UTC-3): isodow 2, hora 22
    rodar(dw, [C("x", t("2023-06-14 01:30"))], com_gold=True)
    assert (2, 22, 1) in [(d, h, n) for d, h, n in linhas(dw, "SELECT dia_semana, hora, conversas FROM gold.agg_uso_hora WHERE pais = 'Brazil'")]


def test_recusa_e_modelo_por_versao(dw):
    rec = "Desculpe, mas nao posso ajudar com isso."
    rodar(dw, [C("a", BASE, modelo="gpt-3.5-turbo-0301", resposta=rec), C("b", BASE, modelo="gpt-3.5-turbo-0301"),
               C("c", BASE, modelo="gpt-4-0125-preview")], com_gold=True)
    r = {m: (n, k) for m, n, k in linhas(dw, "SELECT modelo, conversas_texto, com_recusa FROM gold.agg_recusa_modelo WHERE pais = 'Brazil'")}
    assert r["gpt-3.5-turbo-0301"] == (2, 1) and r["gpt-4-0125-preview"] == (1, 0)
    mes = linhas(dw, "SELECT conversas, conversas_gpt4 FROM gold.agg_modelo_mes WHERE pais = 'Brazil' AND mes = '2023-06-01'")
    assert mes == [(3, 1)]

def test_retorno_por_versao_do_modelo(dw):
    # 3 usuarios da versao 0301 (1 volta em 2 dias) e 2 da gpt-4-0125 (nenhum volta); todos elegiveis
    rodar(dw, [C("a", BASE, modelo="gpt-3.5-turbo-0301"), C("a", BASE + timedelta(days=2)), C("b", BASE, modelo="gpt-3.5-turbo-0301"),
               C("c", BASE, modelo="gpt-3.5-turbo-0301"), C("d", BASE, modelo="gpt-4-0125-preview"), C("e", BASE, modelo="gpt-4-0125-preview")], com_gold=True)
    r = {m: (el, v) for m, el, v in linhas(dw, "SELECT modelo, elegiveis, voltaram_7d FROM gold.agg_recusa_modelo WHERE pais = 'Brazil'")}
    assert r["gpt-3.5-turbo-0301"] == (3, 1) and r["gpt-4-0125-preview"] == (2, 0)

def test_modelo_por_versao_vale_para_pais_sem_texto(dw):
    # fora do Brasil nao ha texto: o retorno por versao existe, a recusa nao (conversas_texto = 0)
    rodar(dw, [C("fa", t("2023-01-01 10:00"), pais="France"), C("fb", t("2023-12-31 10:00"), pais="France"),   # a elegibilidade usa o periodo de cada pais
               C("f1", BASE, pais="France", modelo="gpt-4-0314"), C("f1", BASE + timedelta(days=1), pais="France", modelo="gpt-4-0314"), C("f2", BASE, pais="France", modelo="gpt-4-0314")], com_gold=True)
    assert linhas(dw, "SELECT conversas, conversas_texto, elegiveis, voltaram_7d FROM gold.agg_recusa_modelo WHERE pais = 'France' AND modelo = 'gpt-4-0314'") == [(3, 0, 2, 1)]


def test_retorno_com_e_sem_as_10_pessoas_mais_ativas(dw):
    convs = []
    for i in range(10):                                                    # 10 pessoas "pesadas": 2 conversas com 2 dias de distancia (voltam)
        convs += [C(f"h{i}", BASE), C(f"h{i}", BASE + timedelta(days=2))]
    convs += [C(f"l{i}", BASE) for i in range(5)]                          # 5 leves: 1 conversa, nao voltam
    rodar(dw, convs, com_gold=True)
    v, el_sem, v_sem, el = linhas(dw, "SELECT voltaram_7d, elegiveis_sem_top10, voltaram_sem_top10, usuarios_elegiveis FROM gold.pais WHERE pais = 'Brazil'")[0]
    assert (el, v) == (15, 10)                                             # as 2 ancoras de datas nao sao elegiveis
    assert (el_sem, v_sem) == (5, 0)                                       # tirando as 10 mais ativas sobram as 5 leves, nenhuma voltou
