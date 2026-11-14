"""CONTRATO DA SEMENTE: antes de carregar, confere se cada arquivo Parquet tem as colunas e os tipos que a Bronze espera.
Se a semente mudar de formato (coluna a menos, tipo diferente), a carga para AQUI com uma mensagem clara, em vez de quebrar de forma
obscura no meio da Silver ou, pior, de carregar numeros errados sem ninguem perceber.

Tipos: texto, inteiro, booleano, data_hora (com fuso), estrutura (campo aninhado) e lista (lista de estruturas)."""
from pathlib import Path

import duckdb

_COMUNS = {"conversation_hash": "texto", "model": "texto", "timestamp": "data_hora", "turn": "inteiro", "language": "texto", "country": "texto",
           "state": "texto", "hashed_ip": "texto", "header": "estrutura", "toxic": "booleano", "redacted": "booleano",
           "primeira_resposta_ts": "data_hora"}

CONTRATO = {
    "wildchat_brasil.parquet": {**_COMUNS, "conversation": "lista", "openai_moderation": "lista", "detoxify_moderation": "lista"},
    "wildchat_outros_paises.parquet": dict(_COMUNS),
}


def _tipo(duck: str) -> str:
    d = duck.upper()
    if d.endswith("[]"):
        return "lista"
    if d.startswith("STRUCT"):
        return "estrutura"
    if d.startswith("TIMESTAMP"):
        return "data_hora"
    if d in ("BIGINT", "INTEGER", "HUGEINT", "SMALLINT"):
        return "inteiro"
    if d == "BOOLEAN":
        return "booleano"
    if d == "VARCHAR":
        return "texto"
    return d.lower()


class ContratoQuebrado(Exception):
    """A semente nao tem o formato esperado pela Bronze."""


def verificar_contrato(con: duckdb.DuckDBPyConnection, semente: Path, contrato: dict | None = None) -> list[str]:
    """Devolve a lista de problemas (vazia = tudo certo)."""
    erros = []
    for arquivo, esperado in (contrato or CONTRATO).items():
        caminho = semente / arquivo
        if not caminho.exists():
            erros.append(f"{arquivo}: arquivo ausente")
            continue
        real = {linha[0]: _tipo(linha[1]) for linha in con.execute(f"DESCRIBE SELECT * FROM read_parquet('{caminho.as_posix()}')").fetchall()}
        for coluna, tipo in esperado.items():
            if coluna not in real:
                erros.append(f"{arquivo}: falta a coluna '{coluna}' ({tipo})")
            elif real[coluna] != tipo:
                erros.append(f"{arquivo}: a coluna '{coluna}' era {tipo} e agora e {real[coluna]}")
        for coluna in real.keys() - esperado.keys():
            erros.append(f"{arquivo}: coluna nova nao prevista no contrato: '{coluna}' (a Bronze nao a carregaria)")
    return erros


def exigir_contrato(con, semente: Path) -> None:
    erros = verificar_contrato(con, semente)
    if erros:
        raise ContratoQuebrado("A semente nao bate com o contrato da Bronze:\n  - " + "\n  - ".join(erros))
