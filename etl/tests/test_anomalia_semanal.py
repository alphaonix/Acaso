"""ALERTA SEMANAL: pega o pico de UMA semana (incidente do PDF, 4.2) e diz o que parece ter acontecido e em que camada procurar."""
from datetime import date, timedelta

import pytest

from comum import anomalia_semanal as s
from comum.anomalia_semanal import Semana

INICIO = date(2023, 5, 1)


def serie(novos, voltaram=None, elegiveis=None):
    """Semanas seguidas (segundas-feiras). Sem `voltaram`, usa 25% dos novos; sem `elegiveis`, usa os novos."""
    voltaram = voltaram or [round(n * 0.25) for n in novos]
    elegiveis = elegiveis or list(novos)
    return [Semana(str(INICIO + timedelta(weeks=i)), n, e, v) for i, (n, e, v) in enumerate(zip(novos, elegiveis, voltaram))]


def enderecos(sem, ja_vistos):
    """{semana: (novos, com endereco ja visto)} a partir de uma lista de percentuais."""
    return {w.semana: (w.novos, round(w.novos * p / 100)) for w, p in zip(sem, ja_vistos)}


def alertas(sem, end=None, pais="Brazil"):
    return [s.diagnosticar(p, w, ant, end) for p, w, ant in s.sinalizadas({pais: sem}, {pais: end} if end else None)]


NORMAL = [40, 42, 38, 41, 39, 40]


def test_semanas_normais_nao_alertam():
    assert alertas(serie(NORMAL + [43, 37, 41])) == []


def test_pico_de_novos_sem_aumento_de_retornos_e_denominador_inflado():
    """O sintoma do incidente: os novos quase dobram e quem voltou fica igual."""
    sem = serie(NORMAL + [90], voltaram=[10, 10, 9, 10, 10, 10, 10])
    [a] = alertas(sem)
    assert a.diagnostico == "DENOMINADOR_INFLADO" and a.camada == "SILVER_OU_BRONZE" and a.semana == sem[-1].semana and a.novos == 90


def test_pico_com_enderecos_ja_conhecidos_e_pessoa_dividida():
    """A pista que fecha o diagnostico do incidente: 55% dos 'novos' ja tinham aparecido com outra pessoa (normal: 10%)."""
    sem = serie(NORMAL + [90], voltaram=[10, 10, 9, 10, 10, 10, 10])
    [a] = alertas(sem, enderecos(sem, [10, 10, 10, 10, 10, 10, 55]))
    assert a.diagnostico == "PESSOA_DIVIDIDA" and a.camada == "SILVER" and a.pct_endereco > 50 and "UA_NORM_SQL" in a.resumo


def test_pessoa_dividida_e_pega_mesmo_sem_pico_grande_de_novos():
    """Em dados pequenos o pico de novos e discreto (+10%), mas o endereco ja visto salta de 10% para 40%: o sinal do endereco pega."""
    sem = serie(NORMAL + [46])
    assert alertas(sem) == []                                                         # sem a pista do endereco, passaria despercebido
    [a] = alertas(sem, enderecos(sem, [10, 10, 10, 10, 10, 10, 40]))
    assert a.diagnostico == "PESSOA_DIVIDIDA"


def test_novos_e_retornos_subindo_juntos_e_pico_de_uso():
    sem = serie(NORMAL + [90], voltaram=[10, 10, 9, 10, 10, 10, 23])
    [a] = alertas(sem)
    assert a.diagnostico == "PICO_DE_USO" and a.camada == "SEM_CAUSA"


def test_queda_de_novos_aponta_a_bronze():
    sem = serie(NORMAL + [8, 40, 41])
    [a] = alertas(sem)
    assert a.diagnostico == "QUEDA_DE_NOVOS" and a.camada == "BRONZE"


def test_queda_na_ultima_semana_e_ignorada_pois_pode_estar_incompleta():
    assert alertas(serie(NORMAL + [8])) == []


def test_taxa_da_semana_mudou_com_novos_normais():
    sem = serie(NORMAL + [40], elegiveis=[100] * 7, voltaram=[30, 31, 29, 30, 30, 31, 60])
    [a] = alertas(sem)
    assert a.diagnostico == "TAXA_SEMANAL" and a.camada == "SILVER"


def test_pais_pequeno_nao_e_avaliado():
    assert alertas(serie([5, 6, 5, 4, 6, 5, 40])) == []


def test_poucas_semanas_nao_sao_avaliadas():
    assert alertas(serie([40, 41, 42, 90])) == []


# ------------------------------------------------------------------ dentro da carga (com banco): so o que e NOVO desde a carga anterior reprova
def _gold(dw, novos):
    dw.execute("DELETE FROM gold.agg_retorno_semana")
    for w in serie(novos):
        dw.execute("INSERT INTO gold.agg_retorno_semana (pais, semana, novos, elegiveis, voltaram_7d) VALUES ('Brazil', %s, %s, %s, %s)", (w.semana, w.novos, w.elegiveis, w.voltaram))


def _carga(dw, status="rodando"):
    return dw.execute("INSERT INTO ops.etl_execucao (status) VALUES (%s) RETURNING id", (status,)).fetchone()[0]


def _fechar(dw, exec_id, resultados):
    from comum import qualidade
    qualidade.gravar(dw, exec_id, resultados)
    dw.execute("UPDATE ops.etl_execucao SET status = 'ok' WHERE id = %s", (exec_id,))


def test_primeira_verificacao_e_linha_de_base_e_depois_so_o_novo_reprova(dw):
    _gold(dw, NORMAL + [90, 40, 41])
    a = _carga(dw)
    r = s.verificar(dw, dw, a)[0]
    assert r.passou and r.obtido == "linha de base"                                   # o pico ja existente vira linha de base
    _fechar(dw, a, [r])

    b = _carga(dw)
    r = s.verificar(dw, dw, b)[0]
    assert r.passou                                                                   # o mesmo pico, ja conhecido
    _fechar(dw, b, [r])

    _gold(dw, NORMAL + [90, 40, 41, 40, 39, 41, 40, 95, 40])                          # aparece um pico NOVO
    c = _carga(dw)
    r = s.verificar(dw, dw, c)[0]
    assert not r.passou and r.obtido == "1"
    linha = dw.execute("SELECT semana::text, diagnostico, nova FROM auditoria.anomalia_semanal WHERE execucao_id = %s AND nova", (c,)).fetchone()
    assert linha[2] is True and linha[0] == str(INICIO + timedelta(weeks=13))
