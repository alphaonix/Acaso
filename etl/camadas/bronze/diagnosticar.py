"""Diagnostico da BRONZE: o que ficou na tabela depois da carga (contagens, vazios, periodo). Alimenta o historico e a deteccao de deriva.
Para investigar: SELECT * FROM auditoria.historico_metrica WHERE camada = 'bronze' ORDER BY execucao_id DESC;"""
from comum.diagnostico import Metrica, coletar

_COLUNAS_VAZIAS = ["country", "state", "language", "model", "hashed_ip", '"timestamp"', "primeira_resposta_ts", "header->>'user-agent'", "conversation"]
_NULOS = " UNION ALL ".join(
    f"SELECT '{c.replace(chr(34), '').replace(chr(39), '')}', count(*) FILTER (WHERE {c} IS NULL), NULL FROM bronze.wildchat" for c in _COLUNAS_VAZIAS)

CONSULTAS = [
    ("linhas", "SELECT arquivo_origem, count(*), NULL FROM bronze.wildchat GROUP BY 1"),
    ("linhas_por_pais", "SELECT coalesce(country, '(vazio)'), count(*), NULL FROM bronze.wildchat GROUP BY 1"),
    ("nulos", _NULOS),
    ("periodo", "SELECT NULL, NULL, min(primeira_resposta_ts)::text || ' a ' || max(primeira_resposta_ts)::text FROM bronze.wildchat"),
    ("paises_distintos", "SELECT NULL, count(DISTINCT country), NULL FROM bronze.wildchat"),
    ("conversas_com_texto", "SELECT NULL, count(*), NULL FROM bronze.wildchat WHERE conversation IS NOT NULL"),
]


def diagnosticar_bronze(dw) -> list[Metrica]:
    return coletar(dw, "bronze", CONSULTAS)
