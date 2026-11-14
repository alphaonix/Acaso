"""ETL em camadas: bronze -> silver -> gold, tudo no Postgres, com validacao ao fim de CADA camada (ADR-004).

A receita esta na funcao `carga` (leia-a de cima para baixo):

  preparar   migra o banco, cria as contas de acesso e abre o registro da execucao
  BRONZE     construir_bronze  ->  validar_bronze  ->  medir    (o dado como veio; confere o contrato da semente antes)
  SILVER     construir_silver  ->  auditar_silver  ->  validar_silver  ->  medir   (limpeza, pessoa, visitas, retorno, elegibilidade)
  GOLD       construir_gold  ->  construir_efeitos  ->  auditar_gold  ->  validar_gold  ->  medir   (resumos que a tela le)
  "medir"    grava as medidas da camada no historico e compara com a carga anterior (deriva: numeros que mudaram sem a semente mudar)
  publicar   COMMIT (ou ROLLBACK, se alguma validacao falhar)

As tres camadas sao reconstruidas por inteiro em UMA transacao: a API nunca ve um estado pela metade, e se qualquer validacao
falhar (modo estrito) nada e publicado. Cada camada tem a sua pasta em camadas/ (com um LEIA-ME.md); o que e comum a todas
(banco, contas, regras de negocio, portao de qualidade) fica em comum/. Como a semente foi gerada: semente/.
"""
import json
import os
import time
from pathlib import Path

import duckdb

from camadas import bronze, gold, silver
from comum import acesso, banco, deriva, diagnostico, qualidade

SEMENTE = Path(os.environ.get("SEED_DIR", "/data/seed"))
ESTRITO = os.environ.get("QA_ESTRITO", "1") == "1"           # conferencia falhou: desfaz a carga
DERIVA_ESTRITA = os.environ.get("DERIVA_ESTRITA", "0") == "1"   # deriva (numeros mudaram sem a semente mudar): alerta; com 1, tambem desfaz
VERSAO = os.environ.get("CODE_VERSION", "dev")


class PortaoFalhou(Exception):
    """Uma validacao de camada falhou no modo estrito: a carga e desfeita."""


def conferir(ops, exec_id: int, camada: str, resultados: list[qualidade.Resultado], alertas: list) -> None:
    """Grava o resultado das validacoes da camada, mostra no log e, se alguma falhou no modo estrito, interrompe a carga."""
    qualidade.gravar(ops, exec_id, resultados)
    for r in resultados:
        print(f"[qa] {'OK ' if r.passou else 'FALHOU'} [{r.transicao}] {r.verificacao}: esperado {r.esperado}, obtido {r.obtido}", flush=True)
    falhas = [r for r in resultados if not r.passou]
    alertas.extend(falhas)
    graves = [r for r in falhas if r.transicao != "deriva" or DERIVA_ESTRITA]      # deriva so derruba a carga se DERIVA_ESTRITA=1
    if graves and ESTRITO:
        raise PortaoFalhou(f"{len(graves)} verificacao(oes) da camada {camada} falharam")


def medir(ops, exec_id: int, camada: str, metricas: list) -> list[qualidade.Resultado]:
    """Grava as medidas da camada no historico (auditoria.metrica) e compara com a carga anterior (deriva)."""
    diagnostico.gravar_metricas(ops, exec_id, metricas)
    resultado, linhas = deriva.comparar(ops, exec_id, camada)
    for linha in linhas:
        print(linha, flush=True)
    return [resultado]


def carga(ops, dw, con, exec_id: int, estado: dict) -> list:
    """Constroi e valida as tres camadas, nesta ordem. Devolve as validacoes que falharam (vazio = tudo certo)."""
    alertas: list = []

    print("== BRONZE: o dado como veio ==", flush=True)
    t0 = time.time()
    for arquivo, n in bronze.construir_bronze(ops, dw, con, exec_id, SEMENTE).items():
        print(f"[bronze] {arquivo}: {n} linhas carregadas em {bronze.TABELA}", flush=True)
    estado["bronze_s"] = time.time() - t0
    conferir(ops, exec_id, "bronze", bronze.validar_bronze(dw, exec_id) + medir(ops, exec_id, "bronze", bronze.diagnosticar_bronze(dw)), alertas)

    print("== SILVER: limpeza, pessoa, visitas, retorno, elegibilidade ==", flush=True)
    t1 = time.time()
    dados = silver.construir_silver(dw)
    estado.update(dados)
    print(f"[silver] lidas={dados['lidas']} carregadas={dados['carregadas']} sem_inicio={dados['sem_inicio']} "
          f"sem_ip={dados['sem_ip']} duplicadas={dados['duplicadas']} pais_nulo={dados['pais_nulo']} "
          f"(bronze {estado['bronze_s']:.0f}s, silver {time.time() - t1:.0f}s)", flush=True)
    aud = silver.auditar_silver(dw, exec_id)
    print(f"[auditoria] {aud['excluidas']} linhas excluidas registradas; {aud['exemplos_antes_depois']} exemplos antes/depois", flush=True)
    conferir(ops, exec_id, "silver", silver.validar_silver(dw, exec_id) + medir(ops, exec_id, "silver", silver.diagnosticar_silver(dw)), alertas)

    print("== GOLD: resumos que a tela le ==", flush=True)
    gold.construir_gold(dw)
    print(f"[estimar] {gold.construir_efeitos(dw)} efeitos gravados em gold.efeito_fator", flush=True)
    gold.auditar_gold(dw, exec_id)
    conferir(ops, exec_id, "gold", gold.validar_gold(dw, exec_id) + medir(ops, exec_id, "gold", gold.diagnosticar_gold(dw)), alertas)
    return alertas


def main() -> int:
    ops = banco.conectar(autocommit=True)       # historico (execucao, lotes, conferencias): vale na hora, sobrevive a uma carga que falhe
    banco.migrar(ops)
    acesso.garantir_conta_avaliacao(ops)
    exec_id = banco.abrir_execucao(ops, VERSAO)
    dw = None
    estado: dict = {}
    try:
        con = duckdb.connect()                  # DuckDB so le os Parquet da semente
        dw = banco.conectar(autocommit=False)   # as tres camadas: so valem se a carga inteira terminar bem
        alertas = carga(ops, dw, con, exec_id, estado)
        dw.commit()
        banco.finalizar_execucao(ops, exec_id, "alerta" if alertas else "ok", estado["lidas"], estado["carregadas"],
                                 json.dumps({k: v for k, v in estado.items() if k != "bronze_s"}))
        print(f"ETL concluido ({'com alertas' if alertas else 'ok'}).", flush=True)
        return 0
    except PortaoFalhou as e:
        dw.rollback()
        banco.finalizar_execucao(ops, exec_id, "falhou", estado.get("lidas"), 0, f"{e}; nada publicado.")
        print("ETL: portao de qualidade FALHOU; carga revertida.", flush=True)
        return 1
    except Exception as e:
        if dw is not None:
            dw.rollback()
        banco.finalizar_execucao(ops, exec_id, "erro", obs=str(e)[:500])
        raise


if __name__ == "__main__":
    raise SystemExit(main())
