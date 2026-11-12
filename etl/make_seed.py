"""Gera a SEMENTE versionada no repositorio a partir da base bruta completa (data/raw/wildchat_todos.parquet).

  data/seed/wildchat_brasil.parquet         Brasil, bruto completo (com texto) + primeira_resposta_ts  ~22 MB
  data/seed/wildchat_outros_paises.parquet  demais paises, so metadados (SEM texto) + primeira_resposta_ts  ~35 MB

Por que existe: o repositorio precisa subir com `docker compose up` sem baixar 3 GB nem rodar Python a mao
(ver docs/adr/ADR-002). Rode so quando quiser regenerar a semente:  python etl/make_seed.py
"""
from pathlib import Path
import duckdb

RAIZ = Path(__file__).resolve().parents[1]
BRUTO = RAIZ / "data" / "raw" / "wildchat_todos.parquet"
SEMENTE = RAIZ / "data" / "seed"
SEMENTE.mkdir(parents=True, exist_ok=True)

# Mesma regra para todos os paises: o inicio da conversa e o horario da 1a resposta do assistente (a mensagem 2; as do usuario nao tem horario).
INICIO = "struct_extract(list_extract(conversation, 2), 'timestamp') AS primeira_resposta_ts"

con = duckdb.connect()
con.execute(f"""COPY (SELECT *, {INICIO} FROM read_parquet('{BRUTO.as_posix()}') WHERE country = 'Brazil')
  TO '{(SEMENTE / "wildchat_brasil.parquet").as_posix()}' (FORMAT parquet, COMPRESSION zstd)""")
con.execute(f"""COPY (
  SELECT conversation_hash, model, turn, language, country, state, hashed_ip, header, timestamp, toxic, redacted,
         {INICIO}
  FROM read_parquet('{BRUTO.as_posix()}') WHERE country IS DISTINCT FROM 'Brazil')  -- inclui country nulo (1.060 linhas): nada e descartado em silencio
  TO '{(SEMENTE / "wildchat_outros_paises.parquet").as_posix()}' (FORMAT parquet, COMPRESSION zstd)""")

for f in sorted(SEMENTE.glob("*.parquet")):
    n = con.execute(f"SELECT count(*) FROM read_parquet('{f.as_posix()}')").fetchone()[0]
    print(f"{f.name}: {n} linhas, {f.stat().st_size / 1e6:.1f} MB")
