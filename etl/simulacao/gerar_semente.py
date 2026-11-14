"""Gera sementes ADULTERADAS para teste, em /data/cenarios (a semente oficial, em /data/seed, nunca e tocada).
  nova    quase igual a oficial: 1 conversa do Brasil a menos. Serve de "dado novo e saudavel" (sha256 diferente do oficial).
  bronze  60% das conversas do Brasil chegam SEM endereco (hashed_ip nulo): o defeito nasce na entrada, como se o sistema de origem falhasse.
So o arquivo do Brasil muda; o dos outros paises e copiado igual (o contrato da semente continua valendo: mesmas colunas e tipos)."""
import shutil
from pathlib import Path

import duckdb

ORIGEM = Path("/data/seed")
DESTINO = Path("/data/cenarios")


def gerar() -> None:
    con = duckdb.connect()
    brasil = (ORIGEM / "wildchat_brasil.parquet").as_posix()
    variantes = {
        "nova": f"SELECT * FROM read_parquet('{brasil}') WHERE conversation_hash <> (SELECT min(conversation_hash) FROM read_parquet('{brasil}'))",
        "bronze": f"SELECT * REPLACE (CASE WHEN hash(conversation_hash) % 10 < 6 THEN NULL ELSE hashed_ip END AS hashed_ip) FROM read_parquet('{brasil}')",
    }
    for nome, sql in variantes.items():
        pasta = DESTINO / nome
        pasta.mkdir(parents=True, exist_ok=True)
        con.execute(f"COPY ({sql}) TO '{(pasta / 'wildchat_brasil.parquet').as_posix()}' (FORMAT parquet)")
        destino_outros = pasta / "wildchat_outros_paises.parquet"
        if not destino_outros.exists():
            shutil.copyfile(ORIGEM / "wildchat_outros_paises.parquet", destino_outros)
        n, sem_ip = con.execute(f"SELECT count(*), count(*) FILTER (WHERE hashed_ip IS NULL) FROM read_parquet('{(pasta / 'wildchat_brasil.parquet').as_posix()}')").fetchone()
        print(f"[semente] {nome}: Brasil com {n} conversas, {sem_ip} sem endereco", flush=True)


if __name__ == "__main__":
    gerar()
