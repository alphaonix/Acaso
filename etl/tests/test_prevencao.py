"""PREVENCAO DE DIVERGENCIAS: o que impede um numero de mudar sem ninguem perceber.
  - recalculo independente (Python, a partir da bronze) tem de bater com a silver e PEGAR um erro plantado
  - contrato da semente: coluna a menos, tipo trocado ou coluna nova derrubam a carga
  - deriva: mesma semente => mesmos numeros; semente nova => so variacao grande e apontada
  - diagnostico: medidas por camada, reprodutiveis
"""
from datetime import timedelta

import duckdb
import pytest

from camadas import bronze, gold, silver
from camadas.bronze.contrato import verificar_contrato
from camadas.silver.recalculo_independente import divergencias
from comum import deriva, diagnostico, qualidade
from comum.diagnostico import Metrica

from .helpers import C, UA_CHROME_119, UA_CHROME_120, linhas, rodar, t

BASE = t("2023-06-01 10:00")


def _cenario():
    """Casos variados: retorno, nao retorno, navegador atualizado, sem IP, copia exata, outro pais."""
    return [
        C("a", BASE), C("a", BASE + timedelta(days=3)),                                     # voltou em 3 dias
        C("b", BASE), C("b", BASE + timedelta(days=10)),                                    # voltou so depois de 7 dias
        C("c", BASE, ua=UA_CHROME_119), C("c", BASE + timedelta(days=1), ua=UA_CHROME_120),  # navegador atualizou: mesma pessoa
        C(None, BASE),                                                                      # sem IP: excluida
        C("d", BASE, hash="igual"), C("d", BASE, hash="igual"),                             # copia exata
        C("e", BASE, pais="China"), C("e", BASE + timedelta(hours=5), pais="China"),        # outro pais
        C("f", BASE), C("f", BASE + timedelta(minutes=20)),                                 # 20 min depois: mesma visita
    ]


def test_recalculo_independente_bate_com_a_silver(dw):
    rodar(dw, _cenario())
    r = divergencias(dw)
    assert r["pessoas_comparadas"] >= 6
    assert {k: v for k, v in r.items() if k != "pessoas_comparadas"} == {
        "pessoas_em_um_lado_so": 0, "voltou_7d": 0, "voltou_24h": 0, "elegivel": 0, "primeira_vez": 0, "convs_total": 0}


@pytest.mark.parametrize("coluna,campo", [("voltou_7d", "voltou_7d"), ("elegivel", "elegivel"), ("voltou_24h", "voltou_24h")])
def test_recalculo_independente_pega_um_erro_plantado(dw, coluna, campo):
    """Se a silver errasse uma pessoa, o recalculo apontaria exatamente essa divergencia."""
    rodar(dw, _cenario())
    with dw.cursor() as cur:
        cur.execute(f"UPDATE silver.fato_usuario SET {coluna} = NOT {coluna} WHERE usuario_id = (SELECT usuario_id FROM silver.fato_usuario WHERE pais = 'Brazil' ORDER BY usuario_id LIMIT 1)")
    assert divergencias(dw)[campo] == 1


def test_contrato_da_semente(tmp_path):
    con = duckdb.connect()
    con.execute(f"COPY (SELECT 'x' AS nome, 1::BIGINT AS n, TRUE AS ok) TO '{(tmp_path / 'a.parquet').as_posix()}' (FORMAT parquet)")
    contrato = {"a.parquet": {"nome": "texto", "n": "inteiro", "ok": "booleano"}}
    assert verificar_contrato(con, tmp_path, contrato) == []
    assert any("falta a coluna 'idade'" in e for e in verificar_contrato(con, tmp_path, {"a.parquet": {**contrato["a.parquet"], "idade": "inteiro"}}))
    assert any("'n' era texto e agora e inteiro" in e for e in verificar_contrato(con, tmp_path, {"a.parquet": {**contrato["a.parquet"], "n": "texto"}}))
    assert any("coluna nova nao prevista" in e and "'ok'" in e for e in verificar_contrato(con, tmp_path, {"a.parquet": {"nome": "texto", "n": "inteiro"}}))
    assert any("arquivo ausente" in e for e in verificar_contrato(con, tmp_path, {"b.parquet": {"x": "texto"}}))


def test_contrato_real_bate_com_a_semente_do_repositorio():
    """A semente que vai no repositorio cumpre o contrato (so roda se os arquivos estiverem montados no container de teste)."""
    import os
    from pathlib import Path
    semente = Path(os.environ.get("SEED_DIR", "/data/seed"))
    if not (semente / "wildchat_brasil.parquet").exists():
        pytest.skip("semente nao montada neste container")
    assert verificar_contrato(duckdb.connect(), semente) == []


# ------------------------------------------------------------------ deriva
def _carga(dw, status="ok", sha="aaa", metricas=()):
    i = dw.execute("INSERT INTO ops.etl_execucao (status) VALUES (%s) RETURNING id", (status,)).fetchone()[0]
    dw.execute("INSERT INTO ops.bronze_lote (execucao_id, arquivo, sha256, linhas, tamanho_bytes, tabela_destino) VALUES (%s, 'x.parquet', %s, 1, 1, 'bronze.wildchat')", (i, sha))
    diagnostico.gravar_metricas(dw, i, [Metrica("silver", n, e, v, tx) for n, e, v, tx in metricas])
    return i


def test_deriva_sem_carga_anterior_passa(dw):
    atual = _carga(dw, "rodando", metricas=[("pessoas", "Brazil", 100, None)])
    r, linhas_log = deriva.comparar(dw, atual, "silver")
    assert r.passou and linhas_log == []


def test_deriva_mesma_semente_numeros_iguais_passa(dw):
    _carga(dw, metricas=[("pessoas", "Brazil", 100, None), ("impressao", "", None, "123")])
    atual = _carga(dw, "rodando", metricas=[("pessoas", "Brazil", 100, None), ("impressao", "", None, "123")])
    assert deriva.comparar(dw, atual, "silver")[0].passou


def test_deriva_mesma_semente_qualquer_mudanca_falha(dw):
    _carga(dw, metricas=[("pessoas", "Brazil", 100, None), ("impressao", "", None, "123")])
    atual = _carga(dw, "rodando", metricas=[("pessoas", "Brazil", 101, None), ("impressao", "", None, "999")])
    r, log = deriva.comparar(dw, atual, "silver")
    assert not r.passou and r.obtido == "2" and len(log) == 2 and any("pessoas[Brazil]: 100 -> 101" in l for l in log)


def test_deriva_semente_nova_so_aponta_variacao_grande(dw):
    _carga(dw, sha="velha", metricas=[("pessoas", "Brazil", 100, None)])
    pequena = _carga(dw, "rodando", sha="nova", metricas=[("pessoas", "Brazil", 110, None)])          # +10%: dentro da tolerancia
    assert deriva.comparar(dw, pequena, "silver")[0].passou
    dw.execute("UPDATE ops.etl_execucao SET status = 'falhou' WHERE id = %s", (pequena,))
    grande = _carga(dw, "rodando", sha="nova2", metricas=[("pessoas", "Brazil", 200, None)])         # +100% sobre a carga ok mais recente (a velha)
    assert not deriva.comparar(dw, grande, "silver")[0].passou


def test_deriva_ignora_carga_que_falhou(dw):
    _carga(dw, "ok", metricas=[("pessoas", "Brazil", 100, None)])
    _carga(dw, "falhou", metricas=[("pessoas", "Brazil", 7, None)])
    atual = _carga(dw, "rodando", metricas=[("pessoas", "Brazil", 100, None)])
    assert deriva.comparar(dw, atual, "silver")[0].passou          # compara com a carga ok, nao com a que falhou


def test_deriva_so_compara_medidas_presentes_nas_duas_cargas(dw):
    _carga(dw, metricas=[("pessoas", "Brazil", 100, None)])
    atual = _carga(dw, "rodando", metricas=[("pessoas", "Brazil", 100, None), ("medida_nova", "", 5, None)])
    assert deriva.comparar(dw, atual, "silver")[0].passou          # uma medida nova (codigo evoluiu) nao e deriva


# ------------------------------------------------------------------ diagnostico e executor
def test_diagnostico_por_camada_e_reprodutivel(dw):
    rodar(dw, _cenario(), com_gold=True)
    for camada, funcao in (("bronze", bronze.diagnosticar_bronze), ("silver", silver.diagnosticar_silver), ("gold", gold.diagnosticar_gold)):
        a, b = funcao(dw), funcao(dw)
        assert a and [(m.nome, m.escopo, m.valor, m.texto) for m in a] == [(m.nome, m.escopo, m.valor, m.texto) for m in b]   # duas leituras, mesma medida
        assert {m.camada for m in a} == {camada}
    s = {(m.nome, m.escopo): m for m in silver.diagnosticar_silver(dw)}
    n_pessoas = linhas(dw, "SELECT count(*) FROM silver.fato_usuario WHERE pais = 'Brazil'")[0][0]
    assert s[("pessoas", "Brazil")].valor == n_pessoas
    assert s[("impressao_pessoas", "")].texto not in (None, "")


def test_impressao_da_silver_muda_quando_uma_pessoa_muda(dw):
    rodar(dw, _cenario())
    antes = {(m.nome): m.texto for m in silver.diagnosticar_silver(dw)}["impressao_pessoas"]
    dw.execute("UPDATE silver.fato_usuario SET voltou_7d = NOT voltou_7d WHERE usuario_id = (SELECT usuario_id FROM silver.fato_usuario ORDER BY usuario_id LIMIT 1)")
    depois = {(m.nome): m.texto for m in silver.diagnosticar_silver(dw)}["impressao_pessoas"]
    assert antes != depois


def test_executar_aceita_funcao_no_lugar_do_sql(dw):
    r = qualidade.executar(dw, [("x", "funcao devolve 3", "3", lambda dw: 1 + 2), ("x", "sql devolve 3", "3", "SELECT 1 + 2")], 0)
    assert all(x.passou for x in r)
