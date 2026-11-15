"""Gera sementes ADULTERADAS para teste, em /data/cenarios (a semente oficial, em /data/seed, nunca e tocada). So o arquivo do Brasil muda
(mesmas colunas e tipos: o contrato da semente continua valendo); o dos outros paises e ligado/copiado igual.
  nova          quase igual a oficial: 1 conversa do Brasil a menos. E o "dado novo e saudavel" (sha256 diferente do oficial).
  sem_endereco  60% das conversas do Brasil sem endereco (hashed_ip nulo)
  volume_cai    so 40% das conversas do Brasil (perda de dados no envio)
  sem_horario   50% das conversas do Brasil sem horario da primeira resposta
"""
import os
import shutil
from pathlib import Path

import duckdb

ORIGEM = Path("/data/seed")
DESTINO = Path("/data/cenarios")


def _ligar(origem: Path, destino: Path) -> None:
    """Liga o arquivo grande dos outros paises em vez de copiar (cai para copia se o sistema de arquivos nao deixar)."""
    if destino.exists():
        return
    for tentar in (os.link, os.symlink):
        try:
            tentar(origem, destino)
            return
        except OSError:
            continue
    shutil.copyfile(origem, destino)


def gerar() -> None:
    con = duckdb.connect()
    b = (ORIGEM / "wildchat_brasil.parquet").as_posix()
    src = f"read_parquet('{b}')"
    variantes = {
        "nova": f"SELECT * FROM {src} WHERE conversation_hash <> (SELECT min(conversation_hash) FROM {src})",
        "sem_endereco": f"SELECT * REPLACE (CASE WHEN hash(conversation_hash) % 10 < 6 THEN NULL ELSE hashed_ip END AS hashed_ip) FROM {src}",
        "volume_cai": f"SELECT * FROM {src} WHERE hash(conversation_hash) % 10 < 4",
        "sem_horario": f"SELECT * REPLACE (CASE WHEN hash(conversation_hash) % 10 < 5 THEN NULL ELSE primeira_resposta_ts END AS primeira_resposta_ts) FROM {src}",
    }
    for nome, sql in variantes.items():
        pasta = DESTINO / nome
        pasta.mkdir(parents=True, exist_ok=True)
        alvo = pasta / "wildchat_brasil.parquet"
        con.execute(f"COPY ({sql}) TO '{alvo.as_posix()}' (FORMAT parquet)")
        _ligar(ORIGEM / "wildchat_outros_paises.parquet", pasta / "wildchat_outros_paises.parquet")
        n, sem_ip, sem_ini = con.execute(f"SELECT count(*), count(*) FILTER (WHERE hashed_ip IS NULL), count(*) FILTER (WHERE primeira_resposta_ts IS NULL) "
                                         f"FROM read_parquet('{alvo.as_posix()}')").fetchone()
        print(f"[semente] {nome}: Brasil com {n} conversas, {sem_ip} sem endereco, {sem_ini} sem horario", flush=True)


if __name__ == "__main__":
    gerar()
