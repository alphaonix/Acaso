"""Conexao e migracoes do banco, mais o registro da execucao do ETL (tabela ops.etl_execucao)."""
import os
import sys
import time
from pathlib import Path

import psycopg

MIGRACOES = Path(os.environ.get("MIGRATIONS_DIR", "/migrations"))


def conectar(autocommit: bool, tentativas: int = 30) -> psycopg.Connection:
    """Conecta ao Postgres; se ele ainda nao atende, tenta de novo (ate 30 vezes, 1 s entre as tentativas)."""
    for _ in range(tentativas):
        try:
            return psycopg.connect(os.environ["DATABASE_URL"], autocommit=autocommit)
        except psycopg.OperationalError:
            time.sleep(1)
    sys.exit("ETL: banco indisponivel")


def migrar(ops: psycopg.Connection) -> None:
    """Aplica db/migrations/*.sql em ordem, so os que ainda nao estao em public.schema_migrations (cada arquivo roda uma vez)."""
    ops.execute("CREATE TABLE IF NOT EXISTS public.schema_migrations (arquivo text PRIMARY KEY, aplicada_em timestamptz DEFAULT now())")
    feitas = {r[0] for r in ops.execute("SELECT arquivo FROM public.schema_migrations")}
    for sql in sorted(MIGRACOES.glob("*.sql")):
        if sql.name not in feitas:
            print(f"[migrar] {sql.name}", flush=True)
            ops.execute(sql.read_text(encoding="utf-8"))
            ops.execute("INSERT INTO public.schema_migrations (arquivo) VALUES (%s)", (sql.name,))


def abrir_execucao(ops: psycopg.Connection, versao: str) -> int:
    """Registra o inicio da carga (status 'rodando') e devolve o numero da execucao."""
    return ops.execute("INSERT INTO ops.etl_execucao (versao_codigo) VALUES (%s) RETURNING id", (versao,)).fetchone()[0]


def finalizar_execucao(ops, exec_id: int, status: str, lidas=None, carregadas=None, obs=None) -> None:
    """Fecha o registro: status 'ok', 'alerta', 'falhou' ou 'erro'."""
    ops.execute("UPDATE ops.etl_execucao SET finalizado_em = now(), status = %s, linhas_lidas = %s, linhas_carregadas = %s, observacao = %s WHERE id = %s",
                (status, lidas, carregadas, obs, exec_id))
