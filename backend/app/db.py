"""Acesso ao Postgres com pool de conexoes. O papel api_ro so le gold e ops (ADR-004)."""
import os
from decimal import Decimal

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

_pool = ConnectionPool(os.environ["DATABASE_URL"], min_size=1, max_size=5, kwargs={"row_factory": dict_row}, open=True)


def _numero(v):
    """numeric do Postgres chega como Decimal, que o JSON da API serializaria como TEXTO; a tela espera numeros."""
    return float(v) if isinstance(v, Decimal) else v


def consulta(sql: str, params: tuple = ()) -> list[dict]:
    with _pool.connection() as conn:
        return [{k: _numero(v) for k, v in linha.items()} for linha in conn.execute(sql, params).fetchall()]
