"""Linhagem da BRONZE: para cada arquivo da semente registra nome, sha256 (impressao digital), linhas e tamanho em ops.bronze_lote.
Serve para provar, depois, de qual arquivo exato veio cada numero. Usa a conexao `ops` (automatica: o registro fica mesmo se a carga falhar)."""
import hashlib
import sys
from pathlib import Path

import duckdb

from .carregar import DESTINOS


def registrar_lotes(ops, con: duckdb.DuckDBPyConnection, exec_id: int, semente: Path) -> None:
    for nome, tabela in DESTINOS.items():
        arq = semente / nome
        if not arq.exists():
            sys.exit(f"ETL: semente ausente: {arq} (rode python etl/semente/make_seed.py)")
        sha = hashlib.sha256(arq.read_bytes()).hexdigest()
        linhas = con.execute(f"SELECT count(*) FROM read_parquet('{arq.as_posix()}')").fetchone()[0]
        ops.execute("""INSERT INTO ops.bronze_lote (execucao_id, arquivo, sha256, linhas, tamanho_bytes, tabela_destino)
                       VALUES (%s, %s, %s, %s, %s, %s)""", (exec_id, nome, sha, linhas, arq.stat().st_size, tabela))
        print(f"[bronze] {nome}: {linhas} linhas, sha256 {sha[:12]} -> {tabela}", flush=True)
