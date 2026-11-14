"""Parquet (semente) -> BRONZE (UMA tabela: bronze.wildchat). Copia fiel e consultavel do dado bruto; nada e limpo nem derivado.
Estruturas aninhadas (conversation, header, moderacoes) viram JSON (jsonb), preservando tudo o que veio no arquivo.
Os dois arquivos da semente tem colunas diferentes (os paises sem texto nao tem conversation/moderacoes): cada um e carregado
com a sua lista de colunas na MESMA tabela, e `arquivo_origem` registra de onde veio cada linha.
"""
import tempfile
from pathlib import Path

TABELA = "bronze.wildchat"
DESTINOS = {"wildchat_brasil.parquet": TABELA, "wildchat_outros_paises.parquet": TABELA}


def _json(col: str) -> str:
    """Estrutura aninhada -> texto JSON; remove '\\u0000', que o jsonb do Postgres nao aceita."""
    return f"replace(to_json({col})::VARCHAR, '\\u0000', '') AS {col}"


_COMUNS = ["conversation_hash", "model", '"timestamp"', "turn", "language", "country", "state", "hashed_ip", "header", "toxic", "redacted", "primeira_resposta_ts"]

BRASIL = (_COMUNS + ["conversation", "openai_moderation", "detoxify_moderation", "arquivo_origem"],
          f"""SELECT conversation_hash, model, timestamp, turn, language, country, state, hashed_ip, {_json('header')}, toxic, redacted, primeira_resposta_ts,
                     {_json('conversation')}, {_json('openai_moderation')}, {_json('detoxify_moderation')},
                     'wildchat_brasil.parquet' AS arquivo_origem
              FROM read_parquet('{{arquivo}}')""")
OUTROS = (_COMUNS + ["arquivo_origem"],
          f"""SELECT conversation_hash, model, timestamp, turn, language, country, state, hashed_ip, {_json('header')}, toxic, redacted, primeira_resposta_ts,
                     'wildchat_outros_paises.parquet' AS arquivo_origem
              FROM read_parquet('{{arquivo}}')""")


def _copiar(dw, con, select_sql: str, colunas: list[str]) -> None:
    """Exporta o SELECT do DuckDB em CSV temporario e carrega com COPY (rapido para ~800 mil linhas)."""
    with tempfile.TemporaryDirectory() as d:
        arq = Path(d) / "carga.csv"
        con.execute(f"COPY ({select_sql}) TO '{arq.as_posix()}' (FORMAT csv, HEADER false)")
        with dw.cursor() as cur, cur.copy(f"COPY {TABELA} ({', '.join(colunas)}) FROM STDIN (FORMAT csv)") as cp, open(arq, "rb") as f:
            while chunk := f.read(1 << 20):
                cp.write(chunk)


def carregar(dw, con, semente: Path) -> dict[str, int]:
    """Dentro da transacao `dw` (a tabela ja foi esvaziada): carrega cada arquivo da semente em bronze.wildchat.
    Devolve as linhas carregadas por arquivo de origem."""
    con.execute("SET TimeZone='UTC'")
    linhas = {}
    for nome_arquivo, (colunas, sql) in (("wildchat_brasil.parquet", BRASIL), ("wildchat_outros_paises.parquet", OUTROS)):
        _copiar(dw, con, sql.format(arquivo=(semente / nome_arquivo).as_posix()), colunas)
        with dw.cursor() as cur:
            linhas[nome_arquivo] = cur.execute(f"SELECT count(*) FROM {TABELA} WHERE arquivo_origem = %s", (nome_arquivo,)).fetchone()[0]
    return linhas
