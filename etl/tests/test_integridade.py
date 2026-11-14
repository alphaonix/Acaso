"""INTEGRIDADE: ninguem altera bronze, silver ou gold fora do ETL sem ser percebido (e, por padrao, sem ser barrado).
  - trava de escrita: UPDATE/INSERT/DELETE/TRUNCATE fora da carga e recusado; durante a carga (etl.carga = 'on') passa
  - trava desligada e detectada
  - verificacao: o estado vivo e comparado com o que a ultima carga deixou; qualquer linha alterada, apagada ou acrescentada aparece
"""
from datetime import timedelta

import psycopg
import pytest

import verificacao
from comum import diagnostico
from comum.diagnostico import Metrica  # noqa: F401  (reexport para quem precisar)
from camadas import bronze, gold, silver

from .helpers import C, rodar, t

BASE = t("2023-06-01 10:00")


def _cenario():
    return [C("a", BASE), C("a", BASE + timedelta(days=3)), C("b", BASE), C("b", BASE + timedelta(days=10)), C("e", BASE, pais="China")]


def _publicar(dw):
    """Simula uma carga publicada: constroi as camadas, grava as medidas vivas e marca a execucao como 'ok'."""
    rodar(dw, _cenario(), com_gold=True)
    i = dw.execute("INSERT INTO ops.etl_execucao (status) VALUES ('ok') RETURNING id").fetchone()[0]
    medidas = bronze.diagnosticar_bronze(dw) + silver.diagnosticar_silver(dw) + gold.diagnosticar_gold(dw)
    diagnostico.gravar_metricas(dw, i, medidas)
    return i


# ------------------------------------------------------------------ trava de escrita
def test_a_trava_barra_escrita_fora_da_carga(dw):
    assert dw.execute("SELECT auditoria.proteger_camadas()").fetchone()[0] >= 17
    for sql in ("UPDATE gold.pais SET conversas = 0", "DELETE FROM silver.fato_usuario", "TRUNCATE gold.pais",
                "INSERT INTO silver.dim_tema VALUES (99, 'x')", "UPDATE bronze.wildchat SET country = 'X'"):
        with pytest.raises(psycopg.errors.InsufficientPrivilege, match="Camada protegida"):
            dw.execute(sql)
        dw.rollback()
        dw.execute("SELECT auditoria.proteger_camadas()")      # o rollback desfez a trava criada na transacao; recria


def test_a_trava_deixa_o_etl_escrever_durante_a_carga(dw):
    dw.execute("SELECT auditoria.proteger_camadas()")
    dw.execute("SET LOCAL etl.carga = 'on'")
    dw.execute("INSERT INTO silver.dim_tema VALUES (99, 'x')")
    assert dw.execute("SELECT count(*) FROM silver.dim_tema WHERE tema_id = 99").fetchone()[0] == 1


def test_proteger_camadas_e_idempotente(dw):
    dw.execute("SELECT auditoria.proteger_camadas()")
    assert dw.execute("SELECT auditoria.proteger_camadas()").fetchone()[0] == 0


def test_trava_desligada_e_detectada(dw):
    dw.execute("SELECT auditoria.proteger_camadas()")
    assert verificacao.trava_desligada(dw) == []
    dw.execute("ALTER TABLE gold.pais DISABLE TRIGGER protecao_camada")
    assert verificacao.trava_desligada(dw) == ["gold.pais"]


# ------------------------------------------------------------------ verificacao de integridade
def test_estado_intacto_passa(dw):
    _publicar(dw)
    dw.execute("SELECT auditoria.proteger_camadas()")
    r = verificacao.estado_publicado(dw, dw, None, "manual")
    assert all(x.passou for x in r), [x for x in r if not x.passou]


@pytest.mark.parametrize("sql", [
    "UPDATE silver.fato_usuario SET voltou_7d = NOT voltou_7d WHERE usuario_id = (SELECT min(usuario_id) FROM silver.fato_usuario)",   # 1 pessoa alterada
    "DELETE FROM silver.fato_conversa WHERE conversa_id = (SELECT min(conversa_id) FROM silver.fato_conversa)",                       # 1 conversa a menos
    "UPDATE gold.pais SET conversas = conversas + 1 WHERE pais = 'Brazil'",                                                           # 1 numero da gold
    "UPDATE bronze.wildchat SET country = 'China' WHERE country = 'Brazil' AND bronze_id = (SELECT min(bronze_id) FROM bronze.wildchat WHERE country = 'Brazil')",  # bronze
])
def test_alteracao_fora_do_etl_e_detectada(dw, sql):
    _publicar(dw)
    dw.execute(sql)
    r = verificacao.estado_publicado(dw, dw, None, "manual")
    assert not r[0].passou and int(r[0].obtido) >= 1
    detalhe = dw.execute("SELECT divergencias, detalhe FROM auditoria.verificacao ORDER BY id DESC LIMIT 1").fetchone()
    assert detalhe[0] >= 1 and detalhe[1]


def test_linha_acrescentada_por_fora_e_detectada(dw):
    """Quantidade a mais em uma camada: a impressao digital e a contagem mudam."""
    _publicar(dw)
    dw.execute("INSERT INTO silver.dim_tema VALUES (98, 'intruso')")
    dw.execute("UPDATE gold.pais SET usuarios = usuarios + 5 WHERE pais = 'China'")
    assert not verificacao.estado_publicado(dw, dw, None, "manual")[0].passou


def test_sem_carga_publicada_nao_quebra(dw):
    dw.execute("DELETE FROM ops.etl_execucao")
    assert verificacao.estado_publicado(dw, dw, None, "manual")[0].passou
