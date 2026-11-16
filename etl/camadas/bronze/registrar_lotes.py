"""Linhagem da BRONZE: para cada arquivo da semente registra nome, sha256 (impressao digital), linhas e tamanho em ops.bronze_lote.
Serve para provar, depois, de qual arquivo exato veio cada numero. Usa a conexao `ops` (automatica: o registro fica mesmo se a carga falhar)."""
import hashlib
import sys
from pathlib import Path

import duckdb

from .carregar import DESTINOS


def impressao_da_semente(semente: Path) -> dict[str, str]:
    """sha256 de cada arquivo da semente (nome -> impressao digital). Serve para saber se a semente mudou desde a ultima carga."""
    saida = {}
    for nome in DESTINOS:
        arq = semente / nome
        if not arq.exists():
            sys.exit(f"ETL: semente ausente: {arq} (gere com: docker compose --profile base run --rm baixar-base)")
        saida[nome] = hashlib.sha256(arq.read_bytes()).hexdigest()
    return saida


def registrar_lotes(ops, con: duckdb.DuckDBPyConnection, exec_id: int, semente: Path) -> None:
    digitais = impressao_da_semente(semente)
    for nome, tabela in DESTINOS.items():
        arq = semente / nome
        sha = digitais[nome]
        linhas = con.execute(f"SELECT count(*) FROM read_parquet('{arq.as_posix()}')").fetchone()[0]
        ops.execute("""INSERT INTO ops.bronze_lote (execucao_id, arquivo, sha256, linhas, tamanho_bytes, tabela_destino)
                       VALUES (%s, %s, %s, %s, %s, %s)""", (exec_id, nome, sha, linhas, arq.stat().st_size, tabela))
        print(f"[bronze] {nome}: {linhas} linhas, sha256 {sha[:12]} -> {tabela}", flush=True)
