"""Banco de TESTE descartavel: cria `retencao_teste` no mesmo servidor, aplica as migracoes e apaga no fim.
Cada teste roda numa transacao que termina em ROLLBACK, entao nada vaza de um teste para outro e o banco real nunca e tocado.
Rodar:  docker compose --profile test run --rm testes-etl
"""
import os
import pathlib

import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo

URL = os.environ["DATABASE_URL"]
MIGRACOES = pathlib.Path(os.environ.get("MIGRATIONS_DIR", "/migrations"))
BANCO = "retencao_teste"


@pytest.fixture(scope="session")
def url_teste():
    base = conninfo_to_dict(URL)
    adm = psycopg.connect(make_conninfo(**{**base, "dbname": "postgres"}), autocommit=True)
    adm.execute(f"DROP DATABASE IF EXISTS {BANCO} WITH (FORCE)")
    adm.execute(f"CREATE DATABASE {BANCO}")
    url = make_conninfo(**{**base, "dbname": BANCO})
    with psycopg.connect(url, autocommit=True) as ops:
        for sql in sorted(MIGRACOES.glob("*.sql")):
            ops.execute(sql.read_text(encoding="utf-8"))
    yield url
    adm.execute(f"DROP DATABASE IF EXISTS {BANCO} WITH (FORCE)")
    adm.close()


@pytest.fixture
def dw(url_teste):
    conn = psycopg.connect(url_teste, autocommit=False)
    conn.execute("SET TimeZone = 'UTC'")
    yield conn
    conn.rollback()
    conn.close()